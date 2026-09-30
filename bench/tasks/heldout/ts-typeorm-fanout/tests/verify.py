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
    filename='src/repositories/events.ts'
    result=subprocess.run(['node','/opt/task/tsspan.cjs',str(Path('/opt/task/original')/filename),str(APP/filename),'listEvents'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
    assert result.returncode==0,result.stdout
    info=json.loads(result.stdout)
    assert info['found']==info['originalFound']==1
    assert info['prefixEqual'] and info['suffixEqual'] and info['headerEqual'], 'edits outside listEvents'



def run(name, command):
    result = subprocess.run(command, cwd=APP, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=420)
    (LOG / ('command-' + name + '.log')).write_text(result.stdout)
    assert result.returncode == 0, result.stdout[-4000:]


def hidden():
    target=APP/'test/ridges_hidden.test.ts'
    target.write_bytes(Path('/tests/hidden.test.ts').read_bytes())
    try:
        run('hidden',['./node_modules/.bin/tsx','--test',str(target.relative_to(APP))])
    finally:
        target.unlink()



def main():
    LOG.mkdir(parents=True, exist_ok=True)
    checks=[('source_tree_conservation_before',conservation),('bounded_function',bounded),
            ('compilation',lambda:run('types',['./node_modules/.bin/tsc','--noEmit'])),
            ('regression_visible',lambda:run('visible',['./node_modules/.bin/tsx','--test','test/catalog.test.ts'])),
            ('hidden_behaviour',hidden),('source_tree_conservation_after',conservation)]
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
