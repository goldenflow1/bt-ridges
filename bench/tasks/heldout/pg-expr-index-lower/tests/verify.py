import ast
import hashlib
import json
import stat
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

APP = Path('/app')
LOG = Path('/logs/verifier')
CONFIG = json.loads(Path('/opt/task/config.json').read_text())


def records():
    result = {}
    for path in sorted(APP.rglob('*')):
        name = str(path.relative_to(APP))
        if name in CONFIG.get('new_files', []):
            assert path.is_file() and not path.is_symlink() and stat.S_IMODE(path.lstat().st_mode) == 0o644, 'new migration must be a regular 0644 file'
            continue
        record = {'mode': stat.S_IMODE(path.lstat().st_mode)}
        if path.is_symlink():
            record['link'] = str(path.readlink())
        elif path.is_file():
            record['hash'] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            record['directory'] = True
        if name in CONFIG['allowed']:
            record.pop('hash', None)
        result[name] = record
    return result


def conservation():
    expected = json.loads(Path('/opt/task/manifest.json').read_text())
    assert records() == expected, 'source paths, modes, or protected content changed'


def bounded():
    for filename, symbol in CONFIG['bounded'].items():
        before = Path('/opt/task/original', filename).read_text()
        after = (APP / filename).read_text()
        old = next(n for n in ast.parse(before).body if isinstance(n, ast.FunctionDef) and n.name == symbol)
        new = next(n for n in ast.parse(after).body if isinstance(n, ast.FunctionDef) and n.name == symbol)
        a, b = before.splitlines(True), after.splitlines(True)
        assert a[:old.lineno-1] == b[:new.lineno-1] and a[old.end_lineno:] == b[new.end_lineno:], 'out-of-function edit'
        assert ast.dump(old.args) == ast.dump(new.args), 'signature changed'
        assert (ast.dump(old.returns) if old.returns else None) == (ast.dump(new.returns) if new.returns else None)
        assert ast.get_docstring(old) == ast.get_docstring(new), 'docstring changed'
        assert len(after) < 15000



def permitted_constructs():
    path='library/models.py'
    old=Path('/opt/task/original',path).read_text()
    new=(APP/path).read_text()
    def indexes(text):
        member=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name=='Member')
        meta=next(n for n in member.body if isinstance(n,ast.ClassDef) and n.name=='Meta')
        return next(n for n in meta.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='indexes' for t in n.targets))
    a,b=indexes(old),indexes(new)
    left,right=old.splitlines(True),new.splitlines(True)
    assert left[:a.lineno-1]==right[:b.lineno-1] and left[a.end_lineno:]==right[b.end_lineno:], 'only Meta.indexes may change'
    migration=APP/'library/schema_migrations/0002_email_lookup.py'
    if not migration.exists():
        return
    tree=ast.parse(migration.read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            assert all(alias.name.startswith('django') for alias in node.names), 'only Django imports'
        if isinstance(node,ast.ImportFrom):
            assert node.module and node.module.startswith('django'), 'only Django imports'
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
            assert name not in {'RunSQL','RunPython','RawSQL','eval','exec','open','__import__'}, 'raw SQL and external side effects are forbidden'
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Migration')
    assignments={n.targets[0].id:n.value for n in cls.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
    assert ast.literal_eval(assignments['dependencies'])==[('library','0001_initial')], 'migration dependency changed'
    ops=assignments['operations']
    assert isinstance(ops,ast.List) and len(ops.elts)==1, 'exactly one AddIndex operation'
    op=ops.elts[0]
    assert isinstance(op,ast.Call) and isinstance(op.func,ast.Attribute) and op.func.attr=='AddIndex', 'use AddIndex'



def run(name, command):
    result = subprocess.run(command, cwd=APP, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=420)
    (LOG / ('command-' + name + '.log')).write_text(result.stdout)
    assert result.returncode == 0, result.stdout[-4000:]


def hidden():
    target = APP / 'tests/test_private.py'
    target.write_bytes(Path('/tests/hidden.py').read_bytes())
    try:
        run('hidden', ['pytest', '-p', 'no:cacheprovider', '-v', '-rA', 'tests/test_private.py'])
    finally:
        target.unlink()


def main():
    LOG.mkdir(parents=True, exist_ok=True)
    checks = [('source_tree_conservation_before', conservation), ('bounded_functions', bounded), ('bounded_constructs', permitted_constructs),
              ('ruff_lint', lambda: run('lint', ['ruff', 'check', '--no-cache', 'library/models.py', 'library/schema_migrations'])),
              ('regression_visible', lambda: run('visible', ['pytest', '-p', 'no:cacheprovider', '-v', '-rA', 'tests/test_visible.py'])),
              ('migration_state_check', lambda: run('state', ['python', 'manage.py', 'makemigrations', '--check', '--dry-run'])), ('hidden_behaviour', hidden), ('source_tree_conservation_after', conservation)]
    suite = ET.Element('testsuite', name=CONFIG['task'])
    failures = 0
    for name, function in checks:
        case = ET.SubElement(suite, 'testcase', name=name)
        try:
            function()
        except Exception as error:
            failures += 1
            ET.SubElement(case, 'failure', message=str(error)[:1000]).text = str(error)
    suite.set('tests', str(len(checks)))
    suite.set('failures', str(failures))
    ET.ElementTree(suite).write(LOG / 'junit.xml', encoding='utf-8', xml_declaration=True)
    (LOG / 'reward.txt').write_text('0\n' if failures else '1\n')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
