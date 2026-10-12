"""Small repository-derived repair benchmark, with host-owned hidden tests.

Eleven different functions, isolated by family across 2/3/3/3 splits. These are
curated mutations of real NERVE code, not naturally occurring production bugs.
Passing tests is scoped evidence, never authority to install or execute a patch.
Only macOS sandbox-exec is supported; unavailable isolation fails closed.
"""
import ast
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

SCOPE = 'agentos-repository-repair-v1'
_PUBLIC = {'id', 'family', 'source', 'function', 'requirements', 'revision'}


@dataclass(frozen=True)
class RepairTask:
    public: dict
    original: str
    preamble: str
    checks: tuple


def _function(root, module, name):
    path = root/'src/nerve_awim'/module
    source = path.read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return '\n'.join(source.splitlines()[node.lineno-1:node.end_lineno]) + '\n'


def dataset(repo_root=None):
    """Trusted host dataset; only public_task results may reach a model."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    email = _function(root, 'agent_bridge_v13.py', '_validate_email')
    ident = _function(root, 'memory_v18.py', '_id')
    specs = [
        ('train', 'agent_bridge_v13.py', '_normalise_trim', email,
         '.strip().lower()', '.lower()',
         'Preserve _validate_email(value) on the RAW input before trimming: require a string with raw length1..180, then strip surrounding whitespace and lowercase. Whitespace-only raw strings of length1..180 are valid and return an empty string. Raw length>180 must raise ValueError even when trimming would make it short.',
         ('assert fn("  A@B.COM  ") == "a@b.com"', 'assert fn("MiXeD") == "mixed"',
          'raises(ValueError, fn, "")', 'raises(ValueError, fn, 9)',
          'assert fn(" "*180) == ""', 'assert fn(" "*179+"A") == "a"',
          'assert fn("A"*180) == "a"*180',
          'raises(ValueError, fn, " "*180+"A")', 'raises(ValueError, fn, " "*181)')),
        ('train', 'research_checkpoint_v19.py', '_counter', 'MAX_COUNTER = 2**53 - 1\n',
         'type(value) is not int', 'not isinstance(value, int)',
         'Accept exact int values from0 through2**53-1 inclusive; reject booleans and all other values with ValueError.',
         ('assert fn(0) == 0', 'assert fn(2**53-1) == 2**53-1', 'raises(ValueError, fn, True)',
          'raises(ValueError, fn, -1)', 'raises(ValueError, fn, 2**53)')),
        ('selection', 'learning_study.py', 'canonical', '',
         'sort_keys=True', 'sort_keys=False',
         'Return compact JSON with sorted keys, no NaN, and reject UTF-8 output longer than16384 bytes with ValueError.',
         ('assert fn({"z":1,"a":2}) == \'{"a":2,"z":1}\'',
          'assert fn([1,True,None]) == "[1,true,null]"', 'raises(ValueError, fn, float("nan"))',
          'raises(ValueError, fn, "x"*16384)')),
        ('selection', 'pilot_bundle_v28.py', '_path', '',
         "('', '.', '..')", "('', '.')",
         'Return only safe relative POSIX file paths; reject absolute paths, backslashes, NUL, colons and empty/dot/dotdot components.',
         ('assert fn("src/package/file.py") == "src/package/file.py"', 'raises(ValueError, fn, "a/../secret")',
          'raises(ValueError, fn, "/tmp/file")', 'raises(ValueError, fn, "a//b")',
          'raises(ValueError, fn, "a\\\\b")', 'raises(ValueError, fn, 5)', 'raises(ValueError, fn, True)')),
        ('selection', 'study_statistics_v16.py', 'mcnemar_exact_p', '',
         'k = min(better, worse)', 'k = max(better, worse)',
         'Return the two-sided exact conditional binomial McNemar p-value capped at1; counts must be nonnegative exact ints,total<=10000; no discordances means1.',
         ('assert fn(0,0) == 1.0', 'assert fn(4,0) == 0.125', 'assert fn(0,4) == 0.125',
          'assert fn(2,2) == 1.0', 'raises(ValueError, fn, True, 0)', 'raises(ValueError, fn, 10001,0)')),
        ('retention', 'jev_optional.py', 'numeric_summary',
         "METRICS = frozenset(('completion','abort','violations','goal_penalized','prediction_penalized'))\n",
         'output["completion"] > 1', 'output["completion"] > 2',
         'Require exactly the five METRICS fields, finite nonnegative numbers excluding bool; completion/abort<=1; return sorted-key floats.',
         ('assert fn(dict(completion=1,abort=0,violations=2,goal_penalized=3,prediction_penalized=4))["violations"] == 2.0',
          'raises(ValueError,fn,dict(completion=1.5,abort=0,violations=0,goal_penalized=0,prediction_penalized=0))',
          'raises(ValueError,fn,dict(completion=True,abort=0,violations=0,goal_penalized=0,prediction_penalized=0))',
          'raises(ValueError,fn,{})',
          'result=fn(dict(completion=1,abort=0,violations=2,goal_penalized=3,prediction_penalized=4)); assert all(type(v) is float for v in result.values()); assert list(result) == sorted(result)')),
        ('retention', 'pilot_bundle_v28.py', '_unique', '',
         'if key in result:', 'if False:',
         'Build a dictionary from key/value pairs; any duplicate key must raise ValueError even if its values match.',
         ('assert fn([]) == {}', 'assert fn([("a",1),("b",2)]) == {"a":1,"b":2}',
          'raises(ValueError,fn,[("a",1),("a",2)])', 'raises(ValueError,fn,[("x",1),("x",1)])')),
        ('retention', 'repository_agents_v20.py', 'regex_inventory', '',
         "r'\\bdef\\s+", "r'\\bclass\\s+",
         'Preserve this deliberately lexical inventory: return sorted unique regex matches for def NAME followed by opening parenthesis, including nested definitions.',
         ('assert fn("def z(): pass\\ndef a(): pass") == ["a","z"]',
          'assert fn("def z(): pass\\ndef z(): pass") == ["z"]',
          'assert fn("class A:\\n    def method(self): pass") == ["method"]', 'assert fn("") == []')),
        ('final', 'obsidian_export_v18.py', '_quote',
         '_EMAIL = re.compile(r"\\b[\\w.+-]+@[\\w.-]+\\.[a-z]{2,}\\b", re.I)\n'
         '_URL = re.compile(r"\\bhttps?://[^\\s]+", re.I)\n'
         '_MD = re.compile(r"([\\\\\\x60*_{}\\[\\]()#+!|~])")\n',
         '_EMAIL.sub("[email redacted]", value)', 'value',
         'Mask email and HTTP(S) URLs, HTML-escape angle brackets, escape Markdown punctuation using _MD, and prefix each line with > and a space.',
         ('assert "user@example.com" not in fn("user@example.com")',
          'assert "https://example.org" not in fn("https://example.org")',
          'assert fn("<hi>"+chr(10)+"plain") == "> &lt;hi&gt;"+chr(10)+"> plain"',
          'assert fn("*hi*") == "> "+chr(92)+"*hi"+chr(92)+"*"', 'assert fn("plain") == "> plain"')),
        ('final', 'agentos_learning.py', 'expected_handoff', ident,
         "task['memory_written'] is True", "task['memory_written'] is not False",
         'Validate exact host evidence schema and types. Done requires exit0,artifact true,QA true; explicit failure wins over unknown; memory_saved true only for observed true.',
         ('assert fn(dict(id="t",exit_code=0,artifact_exists=True,qa_passed=True,memory_written=None)) == dict(status="done",passed=True,memory_saved=False)',
          'assert fn(dict(id="t",exit_code=None,artifact_exists=True,qa_passed=True,memory_written=True))["status"] == "unknown"',
          'assert fn(dict(id="t",exit_code=1,artifact_exists=None,qa_passed=True,memory_written=False))["status"] == "failed"',
          'raises(ValueError,fn,dict(id="t",exit_code=True,artifact_exists=True,qa_passed=True,memory_written=False))')),
        ('final', 'regression_v15.py', 'compare', '',
         '"passes":a<=allowed', '"passes":a>=allowed',
         'Compare goal_error and late_prediction_error: finite nonnegative metrics; each candidate<=baseline*(1+tolerance)+1e-12; nonnegative tolerances default0.05; return detailed metrics and aggregate passes.',
         ('assert fn(dict(goal_error=1,late_prediction_error=1),dict(goal_error=1,late_prediction_error=1))["passes"] is True',
          'assert fn(dict(goal_error=2,late_prediction_error=1),dict(goal_error=1,late_prediction_error=1))["passes"] is False',
          'assert fn(dict(goal_error=1.05,late_prediction_error=1),dict(goal_error=1,late_prediction_error=1))["passes"] is True',
          'assert fn(dict(goal_error=1.051,late_prediction_error=1),dict(goal_error=1,late_prediction_error=1))["passes"] is False',
          'raises(ValueError,fn,{},dict(goal_error=1,late_prediction_error=1))',
          'raises(ValueError,fn,dict(goal_error=-1,late_prediction_error=1),dict(goal_error=1,late_prediction_error=1))')),
    ]
    splits = {name: [] for name in ('train','selection','retention','final')}
    for phase, module, name, preamble, old, new, requirements, checks in specs:
        original = _function(root, module, name)
        if original.count(old) != 1:
            raise ValueError('repository source changed; re-review benchmark mutation')
        mutated = original.replace(old, new, 1)
        revision = sha256((module + original + preamble).encode()).hexdigest()
        family = module.removesuffix('.py') + ':' + name
        public = dict(id='repair-'+sha256(family.encode()).hexdigest()[:12], family=family,
                      source=preamble+mutated, function=name, requirements=requirements+
                      ' Return JSON {"code":"..."} containing exactly one function with the same name. No imports, decorators, annotations, nested functions, global/nonlocal, file/network access, introspection, or print. Dependencies above are immutable and supplied by host. Available globals: json,re,PurePosixPath,comb,isfinite. Safe builtins: '+','.join(_BUILTINS)+'. Allowed attributes: '+','.join(sorted(_ATTRS))+'. Preserve signature and use literal defaults. Hidden behavioral tests run in isolated process with CPU/time limits.',
                      revision=revision)
        splits[phase].append(RepairTask(public,original,preamble,tuple(checks)))
    return splits


def reference_solution(task):
    """Host preflight only: never supply this reference to a repair model."""
    if not isinstance(task, RepairTask):
        raise TypeError('host-owned repair task required')
    return {'code': task.original}


def public_task(task):
    if not isinstance(task, RepairTask):
        raise TypeError('host-owned repair task required')
    return deepcopy(task.public)


def task_hash(task):
    value = public_task(task) if isinstance(task, RepairTask) else task
    if type(value) is not dict or set(value) != _PUBLIC:
        raise ValueError('exact public repair schema required')
    return sha256(json.dumps({k:v for k,v in value.items() if k!='id'},sort_keys=True,separators=(',',':')).encode()).hexdigest()


_BUILTINS = ('len','str','int','float','bool','dict','list','set','tuple','frozenset','sorted','sum','min','max',
             'all','any','range','enumerate','zip','isinstance','type','ValueError','TypeError','KeyError','abs','round')
_ATTRS = {'loads','dumps','encode','strip','lower','replace','split','splitlines','join','is_absolute',
          'items','values','keys','get','add','append','sub','compile','fullmatch','findall','I'}
_FORBIDDEN = (ast.Import,ast.ImportFrom,ast.ClassDef,ast.AsyncFunctionDef,ast.Global,ast.Nonlocal,
              ast.With,ast.AsyncWith,ast.Await,ast.Yield,ast.YieldFrom,ast.Delete)


def validate_patch(task, output):
    """Narrow AST capability gate, in addition to OS isolation, never execution."""
    code = output.get('code') if type(output) is dict and set(output)=={'code'} else output
    if type(code) is not str or not 1<=len(code.encode())<=12000:
        raise ValueError('bounded function source required')
    tree = ast.parse(code)
    if len(tree.body)!=1 or type(tree.body[0]) is not ast.FunctionDef or tree.body[0].name!=task.public['function']:
        raise ValueError('one matching replacement function required')
    function = tree.body[0]
    original = ast.parse(task.original).body[0]
    if ast.dump(function.args,include_attributes=False) != ast.dump(original.args,include_attributes=False):
        raise ValueError('original function signature required')
    if function.decorator_list or function.returns or any(a.annotation for a in ast.walk(function.args) if isinstance(a,ast.arg)):
        raise ValueError('decorators and annotations forbidden')
    # Defaults execute at definition time; allow literal defaults only.
    for default in function.args.defaults + [v for v in function.args.kw_defaults if v is not None]:
        ast.literal_eval(default)
    for node in ast.walk(tree):
        if isinstance(node,_FORBIDDEN) or (isinstance(node,ast.FunctionDef) and node is not function):
            raise ValueError('unsupported patch capability')
        if isinstance(node,ast.Name) and (node.id.startswith('__') or node.id in
                {'open','eval','exec','compile','globals','locals','vars','getattr','setattr','delattr','input','print','help','breakpoint','__import__'}):
            raise ValueError('unsupported patch name')
        if isinstance(node,ast.Attribute) and (node.attr not in _ATTRS or not isinstance(node.ctx,ast.Load)):
            raise ValueError('unsupported patch attribute')
    return code


_RUNNER = r'''
import builtins,json,math,pathlib,re,resource,sys
resource.setrlimit(resource.RLIMIT_CPU,(2,2))
resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
hard=resource.getrlimit(resource.RLIMIT_DATA)[1]
limit=min(536870912,hard) if hard>=0 else 536870912
try:
    resource.setrlimit(resource.RLIMIT_DATA,(limit,limit))
    memory_limited=True
except (ValueError,OSError):
    memory_limited=False
payload=json.loads(sys.stdin.read(100000))
safe={k:getattr(builtins,k) for k in payload['builtins']}
def limited_import(name,*args,**kwargs):
    if name=='re': return re
    raise ImportError('module unavailable')
safe['__import__']=limited_import
namespace={'__builtins__':safe,'json':json,'re':re,'PurePosixPath':pathlib.PurePosixPath,
           'comb':math.comb,'isfinite':math.isfinite}
exec(payload['preamble'],namespace)
exec(payload['code'],namespace)
fn=namespace[payload['function']]
def raises(kind,fn,*args,**kwargs):
    try: fn(*args,**kwargs)
    except Exception as error:
        assert type(error) is kind
        return
    raise AssertionError('expected exception')
passed=0
for check in payload['checks']:
    try:
        exec(check,{'fn':fn,'raises':raises})
        passed+=1
    except Exception: pass
print(json.dumps({'passed':passed,'total':len(payload['checks']),'memory_limited':memory_limited}))
'''


def evaluate(task, output, *, timeout=4.0):
    """Run hidden tests in a disposable OS-sandboxed child; never install code."""
    if not isinstance(task, RepairTask):
        raise TypeError('host-owned repair task required')
    if type(timeout) not in (int,float) or not 0.05<=timeout<=10:
        raise ValueError('bounded sandbox timeout required')
    result = dict(passed=False,category='patch_rejected',tests_passed=0,tests_total=len(task.checks),scope=SCOPE)
    try:
        code = validate_patch(task,output)
    except (ValueError,SyntaxError,TypeError,RecursionError):
        return result
    if sys.platform!='darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        return dict(result,category='sandbox_unavailable')
    with tempfile.TemporaryDirectory(prefix='nerve-repair-') as tmp:
        directory=Path(tmp).resolve()
        runner=directory/'runner.py'
        runner.write_text(_RUNNER)
        python=Path(sys.executable).resolve()
        runtime=Path(sys.base_prefix).resolve()
        quoted=lambda p: json.dumps(str(p))
        profile=('(version 1)(deny default)(allow process-exec)(allow process-info*)(allow sysctl-read)'
            '(deny network*)(allow file-read-metadata)(allow mach-lookup)(allow file-read* '+
            ' '.join('(subpath '+quoted(p)+')' for p in (runtime,Path('/System/Library'),Path('/usr/lib')))+
            ' (literal "/") (literal '+quoted(runner)+') (literal "/dev/urandom") (literal "/dev/null"))')
        payload=dict(code=code,preamble=task.preamble,function=task.public['function'],checks=task.checks,builtins=_BUILTINS)
        try:
            process=subprocess.Popen(['/usr/bin/sandbox-exec','-p',profile,str(python),'-I','-S',str(runner)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=directory,
                env={'HOME':str(directory),'TMPDIR':str(directory),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},start_new_session=True)
            try:
                stdout,stderr=process.communicate(json.dumps(payload),timeout=timeout)
            except subprocess.TimeoutExpired:
                import os
                os.killpg(process.pid,signal.SIGKILL)
                process.communicate()
                return dict(result,category='timeout')
            if process.returncode:
                return dict(result,category='sandbox_unavailable' if 'sandbox_apply:' in stderr else 'execution_failed')
            report=json.loads(stdout)
            if (type(report) is not dict or set(report)!={'passed','total','memory_limited'} or type(report['passed']) is not int
                    or type(report['memory_limited']) is not bool or report['total']!=len(task.checks) or not 0<=report['passed']<=len(task.checks)):
                return dict(result,category='invalid_runner_report')
            passed=report['passed']==len(task.checks)
            return dict(result,passed=passed,category='passed' if passed else 'behavior_failed',tests_passed=report['passed'],memory_limit_enforced=report['memory_limited'])
        except (OSError,ValueError):
            return dict(result,category='sandbox_unavailable')
