"""Split a test that loops over variants into one test per variant.

Each variant of a long evidence-chain test rebuilds the whole chain, so one method looping over four variants
is one four-times-longer unit that `run_tests.py --per-test` cannot spread across shards. Mark the method with
`@variants(VALUES)`, loop over `self.variants` in its body, and decorate the class with `@expand_variants`:
every value becomes its own test, `test_name__value`, which sees only its value in `self.variants`.
"""
import functools
import re


def variants(values):
    def mark(method):
        method.variant_values = tuple(values)
        return method
    return mark


def label(value):
    head = value[0] if isinstance(value, (tuple, list)) and value else value
    return re.sub(r'\W+', '_', str(getattr(head, 'NAME', head))).strip('_')


def expand_variants(cls):
    for name, method in list(vars(cls).items()):
        values = getattr(method, 'variant_values', None)
        if values is None:
            continue
        delattr(cls, name)
        taken = set()
        for index, value in enumerate(values):
            suffix = label(value) or str(index)
            if suffix in taken:
                suffix = f'{suffix}_{index}'
            taken.add(suffix)

            @functools.wraps(method)
            def run(self, method=method, value=value):
                self.variants = (value,)
                return method(self)
            run.__name__ = run.__qualname__ = f'{name}__{suffix}'
            del run.variant_values
            setattr(cls, run.__name__, run)
    return cls
