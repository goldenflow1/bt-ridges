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
    for filename in CONFIG['allowed']:
        candidate = ast.parse((APP / filename).read_text())
        original = ast.parse((Path('/opt/task/original') / filename).read_text())
        for old in original.body:
            if isinstance(old, ast.FunctionDef) and not old.name.startswith('_'):
                matches = [node for node in candidate.body if isinstance(node, ast.FunctionDef) and node.name == old.name]
                assert len(matches) == 1, 'public function removed or duplicated'
                new = matches[0]
                assert ast.dump(old.args) == ast.dump(new.args), 'public signature changed'
                assert (ast.dump(old.returns) if old.returns else None) == (ast.dump(new.returns) if new.returns else None), 'public return annotation changed'
        for node in ast.walk(candidate):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert ast.dump(node) in [ast.dump(n) for n in ast.walk(original) if isinstance(n, (ast.Import, ast.ImportFrom))], 'new imports are outside the task contract'
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ''
                assert name not in {'open', 'exec', 'eval', '__import__', 'compile', 'system', 'popen', 'commit'}, 'side-effect construct'
                if CONFIG['task'] in {'py-sqla-latest-per-customer', 'py-django-not-in-null'}:
                    assert name not in {'text', 'exec_driver_sql', 'raw', 'extra', 'cursor'}, 'raw SQL prohibited'
        if CONFIG['task'] == 'py-sqla-partial-index':
            fields = {'revision', 'down_revision', 'branch_labels', 'depends_on'}
            def assignments(tree, fields=fields):
                return {n.targets[0].id: ast.dump(n.value) for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in fields}
            assert assignments(candidate) == assignments(original), 'migration identity changed'
            for symbol in ['upgrade', 'downgrade']:
                old = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == symbol)
                new = next(n for n in candidate.body if isinstance(n, ast.FunctionDef) and n.name == symbol)
                assert ast.dump(old.args) == ast.dump(new.args), 'migration signature changed'
            for node in ast.walk(candidate):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'op':
                        assert node.func.attr in {'create_index', 'drop_index'}, 'only index operations permitted'


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
              ('ruff_lint', lambda: run('lint', ['ruff', 'check', '--no-cache', *CONFIG['allowed']])),
              ('regression_visible', lambda: run('visible', ['pytest', '-p', 'no:cacheprovider', '-v', '-rA', 'tests/test_visible.py'])),
              ('hidden_behaviour', hidden), ('source_tree_conservation_after', conservation)]
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
