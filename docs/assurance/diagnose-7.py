import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".ai/scripts"))
import assurance_measure as m
original = m.observe
def observe(session, reqs, *args):
    items = original(session, reqs, *args)
    print(items)
    return items
m.observe = observe
print(m.measure(only=("handoff",)))
