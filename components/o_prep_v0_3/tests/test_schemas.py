import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
from o_prep import evaluate_signal
from test_o_prep import signal
try:
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:
    Draft202012Validator = None


@unittest.skipIf(Draft202012Validator is None, 'jsonschema optional dependency unavailable')
class SchemaTests(unittest.TestCase):
    def test_input_signal_validates(self):
        x=json.loads((ROOT/'schemas'/'signal.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(x)
        Draft202012Validator(x).validate(signal())

    def test_output_decision_validates(self):
        x=json.loads((ROOT/'schemas'/'decision.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(x)
        Draft202012Validator(x).validate(evaluate_signal(signal('CLOSE')))

    def test_unexpected_authority_is_schema_rejected(self):
        x=json.loads((ROOT/'schemas'/'decision.schema.json').read_text(encoding='utf-8'))
        y=evaluate_signal(signal());y['host_mutation_authorized']=True
        with self.assertRaises(ValidationError):Draft202012Validator(x).validate(y)

    def test_unexpected_codepath_field_is_rejected(self):
        x=json.loads((ROOT/'schemas'/'signal.schema.json').read_text(encoding='utf-8'))
        y=signal();y['exec_unaudited']=True
        with self.assertRaises(ValidationError):Draft202012Validator(x).validate(y)
