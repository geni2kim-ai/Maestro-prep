"""No host paths, secrets, public repository downloads or real node execution."""
from __future__ import annotations

import hashlib
import json
import tempfile
import warnings
import stat
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools.local_node_preflight import run

sha = lambda data: hashlib.sha256(data).hexdigest()


class NodeBytePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source/'README.md').write_bytes(b'safe candidate\n')
        manifest = {
            'schema':'MAESTRO_PREP_PACKAGE_V1','version':'preflight-test',
            'file_count':1,'files':[{'path':'README.md','bytes':15,'sha256':sha(b'safe candidate\n')}],
            'evidence_boundary':{'synthetic':True},
        }
        (self.source/'MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8')
        self.readme_sha = sha(b'safe candidate\n')
        (self.source/'SHA256SUMS.txt').write_text(f"{self.readme_sha}  README.md\n",encoding='utf-8')
        self.zip = self.base/'candidate.zip'
        self.rezip()
        self.astra = self.base/'approved-astra'
        self.astra.mkdir()
        entries={
            'SKILL.md':b'ASTRA SKILL\n',
            'scripts/validate_prework.py':b'print("fake synthetic validator")\n',
            'schemas/prework-plan.schema.json':b'{}\n',
            'profiles/ai-maestro.md':b'Synthetic profile\n',
            'references/evidence-model.md':b'Synthetic evidence policy\n',
            'references/domain-checks.md':b'Synthetic domain rules\n',
        }
        for name, payload in entries.items():
            p=self.astra/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(payload)
        hashes={name:sha(raw) for name,raw in entries.items()}
        agg=sha(''.join(f'{name}  {hashes[name]}\n' for name in sorted(hashes)).encode())
        manifest={'file_count':len(entries),'files':hashes,'bundle_aggregate_sha256':agg}
        astra_manifest=self.astra/'CANDIDATE_HASHES.json'
        astra_manifest.write_text(json.dumps(manifest,sort_keys=True),encoding='utf-8')
        self.router=self.base/'leonardo-router.bin';self.router.write_bytes(b'SYNTHETIC ROUTER')
        self.policy=self.base/'leonardo-policy.json';self.policy.write_bytes(b'{"synthetic":true}')
        lock={'schema':'MAESTRO_PREP_LOCK_V1','astra':{'skill_sha256':hashes['SKILL.md'],
              'approved_version_label':'TEST_V71_SYNTHETIC','official_v71':{
              'validator_sha256':hashes['scripts/validate_prework.py'],
              'schema_sha256':hashes['schemas/prework-plan.schema.json'],
              'profile_sha256':hashes['profiles/ai-maestro.md'],
              'manifest_sha256':sha(astra_manifest.read_bytes())}},
              'leonardo':{'router_version':'SYNTHETIC','policy_sha256':sha(self.policy.read_bytes())}}
        self.lock=self.base/'owner-lock.json';self.lock.write_text(json.dumps(lock,sort_keys=True),encoding='utf-8')
        self.evidence=self.base/'evidence';self.evidence.mkdir()

    def rezip(self):
        with zipfile.ZipFile(self.zip,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(self.source.iterdir()):
                z.write(p,p.name)
        self.zipsha=sha(self.zip.read_bytes())

    def args(self):
        return {'source_root':self.source,'candidate_zip':self.zip,
                'candidate_zip_sha256':self.zipsha,
                'lock_path':self.lock,'lock_sha256':sha(self.lock.read_bytes()),
                'astra_root':self.astra,'leonardo_router':self.router,
                'leonardo_router_sha256':sha(self.router.read_bytes()),
                'leonardo_policy':self.policy,'evidence_root':self.evidence}

    def invoke(self,**kwargs):
        args=self.args();args.update(kwargs);return run(**args)

    def test_complete_synthetic_pins_are_only_preflight(self):
        x=self.invoke()
        self.assertEqual(x['status'],'BYTES_VERIFIED_OWNER_PILOT_REVIEW_REQUIRED',x)
        self.assertEqual(len(x['checks']),6)
        self.assertFalse(x['node_mutation_performed'])
        self.assertIn('LIVE_NODE_INSTALL',x['not_run'])

    def test_no_owner_lock_never_promotes(self):
        x=self.invoke(lock_path=None,lock_sha256=None)
        self.assertEqual(x['status'],'HOLD')
        self.assertEqual(x['checks']['owner_lock_bytes']['code'],'OWNER_LOCK_REQUIRED')

    def test_owner_lock_bytes_differ_hold(self):
        x=self.invoke(lock_sha256='f'*64)
        self.assertEqual(x['status'],'HOLD')
        self.assertEqual(x['checks']['owner_lock_bytes']['code'],'OWNER_LOCK_BYTES_MISMATCH')

    def test_public_or_other_unpinned_astra_diff_hold(self):
        (self.astra/'references/domain-checks.md').write_text('NEW UNAPPROVED DOMAINS')
        x=self.invoke()
        self.assertEqual(x['checks']['approved_astra_full_manifest']['status'],'HOLD')

    def test_leonardo_router_binary_tamper_hold(self):
        bound=self.args()
        self.router.write_bytes(b'OTHER')
        x=run(**bound)
        self.assertEqual(x['checks']['leonardo_local_bytes']['code'],'LEONARDO_ROUTER_PIN_MISMATCH')

    def test_leonardo_policy_tamper_hold(self):
        self.policy.write_bytes(b'UNAPPROVED_POLICY')
        x=self.invoke()
        self.assertEqual(x['checks']['leonardo_local_bytes']['code'],'LEONARDO_POLICY_PIN_MISMATCH')

    def test_candidate_zip_tamper_hold(self):
        self.zip.write_bytes(self.zip.read_bytes()+b'EXTRA')
        x=self.invoke()
        self.assertEqual(x['checks']['source_archive_and_extraction']['code'],'CANDIDATE_ZIP_PIN_MISMATCH')

    def test_candidate_extracted_file_tamper_hold(self):
        (self.source/'README.md').write_text('CHANGED!')
        x=self.invoke()
        self.assertEqual(x['checks']['source_archive_and_extraction']['status'],'HOLD')

    def test_evidence_root_isolated(self):
        x=self.invoke(evidence_root=self.source)
        self.assertEqual(x['checks']['evidence_root']['code'],'EVIDENCE_ROOT_COLOCATED_WITH_SOURCE_OR_PINS')

    def test_source_only_is_explicit_hold(self):
        x=run(source_root=self.source,candidate_zip=self.zip,candidate_zip_sha256=self.zipsha)
        self.assertEqual(x['status'],'HOLD')
        self.assertEqual(x['checks']['source_archive_and_extraction']['status'],'PASS')
        self.assertIn('LEONARDO_EXECUTION',x['not_run'])

    def test_disallows_zip_duplicate_member(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.zip,'a') as z:
                z.writestr('README.md','unsafe duplicate')
        x=self.invoke(candidate_zip_sha256=sha(self.zip.read_bytes()))
        self.assertEqual(x['checks']['source_archive_and_extraction']['code'],'CANDIDATE_ZIP_INVENTORY_UNSAFE')

    def test_extra_untracked_payload_in_zip_rejected(self):
        with zipfile.ZipFile(self.zip,'a') as z:
            z.writestr('unlisted.py','print("unsanctioned")')
        x=self.invoke(candidate_zip_sha256=sha(self.zip.read_bytes()))
        self.assertEqual(x['checks']['source_archive_and_extraction']['code'],'CANDIDATE_ZIP_INVENTORY_UNSAFE')

    def test_symlink_member_in_zip_rejected(self):
        other=self.base/'symlink.zip'
        with zipfile.ZipFile(other,'w') as z:
            for p in sorted(self.source.iterdir()):
                inf=zipfile.ZipInfo(p.name)
                inf.create_system=3
                inf.external_attr=((stat.S_IFLNK|0o777)<<16) if p.name=='README.md' else ((stat.S_IFREG|0o644)<<16)
                z.writestr(inf,p.read_bytes())
        x=self.invoke(candidate_zip=other,candidate_zip_sha256=sha(other.read_bytes()))
        self.assertEqual(x['checks']['source_archive_and_extraction']['code'],'CANDIDATE_ZIP_NONREGULAR_ENTRY')

    def test_symlinked_evidence_root_is_held(self):
        link=self.base/'evidence-link'
        try:link.symlink_to(self.evidence,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('Symlink unavailable')
        x=self.invoke(evidence_root=link)
        self.assertEqual(x['checks']['evidence_root']['code'],'EVIDENCE_ROOT_UNSAFE_OR_MISSING')

if __name__=='__main__':unittest.main()
