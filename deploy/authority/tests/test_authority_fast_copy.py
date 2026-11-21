"""The fixture copy helper must behave like deepcopy for the documents fakes return."""
import backend_test_support
import copy
import unittest

from backend_test_support import fast_copy


class Opaque:
    def __init__(self): self.items = [1, 2]
    def __eq__(self, other): return type(other) is Opaque and other.items == self.items


class FastCopy(unittest.TestCase):
    def document(self):
        return dict(a=[1, 2, dict(b='x', c=None, d=True, e=1.5)], t=(1, [2], dict(k=b'raw')), s='text', n=dict(m=dict(o=[])))

    def test_equal_and_independent_at_every_depth(self):
        original = self.document(); expected = copy.deepcopy(original); value = fast_copy(original)
        self.assertEqual(value, expected)
        value['a'][2]['b'] = 'changed'; value['t'][1].append(3); value['n']['m']['o'].append(1); value['a'].append(9)
        self.assertEqual(original, expected)
        self.assertIsNot(value['a'], original['a']); self.assertIsNot(value['t'][2], original['t'][2])

    def test_types_are_preserved(self):
        value = fast_copy(self.document())
        self.assertIs(type(value['t']), tuple)
        self.assertIs(type(value['a'][2]['d']), bool); self.assertIs(type(value['a'][2]['e']), float)
        self.assertIs(type(value['t'][2]['k']), bytes)
        self.assertEqual(value, self.document())
        self.assertNotEqual(fast_copy([1, 2]), (1, 2))

    def test_unknown_objects_fall_back_to_deepcopy(self):
        original = dict(o=Opaque()); value = fast_copy(original)
        self.assertEqual(value, original)
        self.assertIsNot(value['o'], original['o']); self.assertIsNot(value['o'].items, original['o'].items)


if __name__ == '__main__': unittest.main()
