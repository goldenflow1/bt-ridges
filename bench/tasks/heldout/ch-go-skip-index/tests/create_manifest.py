import json
import shutil
from pathlib import Path

from verify import APP, CONFIG, records

root = Path('/opt/task')
(root / 'manifest.json').write_text(json.dumps(records(), sort_keys=True))
for filename in CONFIG['allowed']:
    if not (APP / filename).exists():
        continue
    target = root / 'original' / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(APP / filename, target)
