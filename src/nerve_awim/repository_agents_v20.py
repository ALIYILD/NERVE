"""Read-only tools for a real repository task: top-level Python function inventory.

No submitted Python is executed. The learner executes registered tools; a
separate token-stream evaluator checks outputs without using the AST handler.
"""
import ast
import io
import re
import tokenize
import unicodedata

from .agent_learning_v12 import RegisteredStrategy

CONTEXT = 'python_top_level_functions'


def regex_inventory(source):
    """Existing-style naive inventory; includes nested definitions and methods."""
    return sorted(set(re.findall(r'\bdef\s+(\w+)\s*\(', source)))


def ast_inventory(source):
    tree = ast.parse(source)
    return sorted({node.name for node in tree.body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))})


def token_inventory(source):
    """Independent indentation/token check, including top-level async defs."""
    depth = 0
    waiting_for_name = False
    names = set()
    name, name_end = None, None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if name is not None:
            # Before Python 3.12 tokenize splits some valid Unicode identifier
            # continuations (notably combining marks) into ERRORTOKEN/NAME.
            if (token.start == name_end and token.type in (tokenize.NAME, tokenize.ERRORTOKEN)
                    and (name + token.string).isidentifier()):
                name, name_end = name + token.string, token.end
                continue
            names.add(unicodedata.normalize('NFKC', name))
            name = None
        if token.type == tokenize.INDENT:
            depth += 1
        elif token.type == tokenize.DEDENT:
            depth -= 1
        elif waiting_for_name:
            if token.type != tokenize.NAME:
                raise ValueError('invalid function declaration')
            # Python's parser stores identifiers in NFKC form. Compare the same
            # semantic name without calling the AST strategy from the judge.
            name, name_end = token.string, token.end
            waiting_for_name = False
        elif token.type == tokenize.NAME and token.string == 'def' and depth == 0:
            waiting_for_name = True
    return sorted(names)


def repository_judge(task, value):
    if task.context != CONTEXT or type(value) is not list:
        return False
    return value == token_inventory(task.payload)


REPOSITORY_STRATEGIES = (
    RegisteredStrategy('regex-inventory', CONTEXT, regex_inventory),
    RegisteredStrategy('ast-inventory', CONTEXT, ast_inventory),
)
