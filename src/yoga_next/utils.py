
import re
import ast
import logging
import sys
from datetime import datetime
import os
import typer
import subprocess

# Create directory traj/YYYY-MM-DD if not exists
# Create directory traj/YYYY-MM-DD if not exists
base_dir = "traj"
date_str = datetime.now().strftime("%Y-%m-%d")
log_dir = os.path.join(base_dir, date_str)
os.makedirs(log_dir, exist_ok=True)

# Log file named with full date and time, e.g., 2024-06-01 15-30-45.txt
timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
log_file = os.path.join(log_dir, f"{timestamp}.txt")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file)
        # logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def log_info(msg: str):
    typer.secho(msg, fg=typer.colors.GREEN)
    logger.info(msg)

def log_warn(msg: str):
    typer.secho(msg, fg=typer.colors.YELLOW)
    logger.warning(msg)

def log_error(msg: str):
    typer.secho(msg, fg=typer.colors.RED, err=True)
    logger.error(msg)


def extract_fenced_code_blocks(text, fence='```'):
    """
    Extract fences with optional language specifier.
    Returns list of code block contents.
    """
    pattern = rf'{re.escape(fence)}[^\n]*\n(.*?){re.escape(fence)}'
    blocks = re.findall(pattern, text, re.DOTALL)
    return blocks

def extract_function_calls(code_str):
    """
    Extract function calls from code_str using balanced parentheses scanning.
    Yields tuples (func_name, arg_str).
    """
    pattern = re.compile(r'(\w+)\s*\(')
    pos = 0
    length = len(code_str)
    
    while pos < length:
        m = pattern.search(code_str, pos)
        if not m:
            break
        func_name = m.group(1)
        start = m.end()  # position after '('
        depth = 1
        i = start
        while i < length and depth > 0:
            c = code_str[i]
            if c == '(':
                depth +=1
            elif c == ')':
                depth -=1
            i +=1
        if depth == 0:
            arg_str = code_str[start:i-1].strip()
            yield func_name, arg_str
            pos = i
        else:
            # no matching closing paren
            break

def split_args_robust(arg_str: str):
    args = []
    current = []
    paren_level = 0
    square_bracket_level = 0
    curly_bracket_level = 0
    in_single_quote = False
    in_double_quote = False
    escape = False
    
    for c in arg_str:
        if escape:
            current.append(c)
            escape = False
            continue
        
        if c == '\\':
            current.append(c)
            escape = True
            continue
        
        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(c)
            continue
        
        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(c)
            continue
        
        if not in_single_quote and not in_double_quote:
            if c == '(':
                paren_level += 1
            elif c == ')':
                if paren_level > 0:
                    paren_level -= 1
            elif c == '[':
                square_bracket_level += 1
            elif c == ']':
                if square_bracket_level > 0:
                    square_bracket_level -= 1
            elif c == '{':
                curly_bracket_level += 1
            elif c == '}':
                if curly_bracket_level > 0:
                    curly_bracket_level -= 1
            elif c == ',' and paren_level == 0 and square_bracket_level == 0 and curly_bracket_level == 0:
                arg = ''.join(current).strip()
                if arg:
                    args.append(arg)
                current = []
                continue
        
        current.append(c)
    
    arg = ''.join(current).strip()
    if arg:
        args.append(arg)
    
    return args

def parse_kwargs_loose(code_str):
    calls = []
    for func_name, arg_str in extract_function_calls(code_str):
        arg_list = split_args_robust(arg_str)
        kwargs = {}
        for arg in arg_list:
            if '=' in arg:
                key, value = arg.split('=', 1)
                val_str = value.strip()
                try:
                    val_parsed = ast.literal_eval(val_str)
                except Exception:
                    # fallback: keep raw string as is (no parsing)
                    val_parsed = val_str
                kwargs[key.strip()] = val_parsed
            else:
                # positional arg, ignore or store if you want
                pass
        calls.append({func_name: kwargs})
    return calls

def extract_json_from_model_markdown_output(content: str) -> dict:
    content = f'\n{content}'
    sections = content.split('\n### ')
    logger.debug(f'Sections: {sections}')
    result = {}
    if sections:
        for section in sections[1:]:
            header_content = section.split('\n', 1)
            header = header_content[0].strip()
            cont = header_content[1].strip() if len(header_content) > 1 else ""
            result[header] = cont
    logger.debug(f"Parsed output: {result}")
    agent_output_dict = dict()
    agent_output_dict['current_state'] = {
        "evaluation_previous_goal": result.get('Current State', ''),
        "memory": result.get('Memory', ''),
        "next_goal": result.get('Next Step', ''),
        'cwd': result.get('Working Directory', '')
    }

    action_section = result.get('Action', '')

    # Extract fenced code blocks from Action
    code_blocks = extract_fenced_code_blocks(action_section)
    logger.debug(f"Extracted code blocks: {code_blocks}")

    actions = []
    for block in code_blocks:
        calls = parse_kwargs_loose(block)
        actions.extend(calls)
        
        # for call_node in calls:
        #     actions.append(ast_call_to_dict(call_node))

    logger.info(f"Actions: {actions}")

    action_list = []
    for a in actions:
        for k in a:
            action_list.append({
                "action_name": k,
                "action_params": a[k]
            })
    logger.debug(f"Action List: {action_list}")
    agent_output_dict['action'] = action_list
    return agent_output_dict


def generate_function_docstring(
    name: str,
    description: str,
    args: dict[str, dict[str, str]],
) -> str:
    """
    Generate Python function signature and docstring from metadata.

    Args:
        name (str): Function/tool name.
        description (str): Function/tool description.
        args (dict): Argument metadata dict, where keys are arg names and values
                     have 'title' and 'type'.

    Returns:
        str: Python function as a string with signature and a docstring.
    """
    # Build function argument string with type hints
    param_list = []
    for arg_name, meta in args.items():
        # print(meta)
        if('anyOf' in meta):
            meta['type'] = meta['anyOf'][0]['type']
        arg_type = meta.get("type", "Any")
        # Map JSON types to Python types (optional, simple mapping)
        type_mapping = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            # extend as needed
        }
        py_type = type_mapping.get(arg_type.lower(), "Any")
        param_list.append(f"{arg_name}: {py_type}")
    params_str = ", ".join(param_list)

    # Build docstring lines
    doc_lines = [f'\t"""\n\t{description}\n']
    for arg_name, meta in args.items():
        title = meta.get("title", arg_name)
        arg_anno = meta.get("description", arg_name)
        arg_type = meta.get("type", "Any")
        default_value = meta.get("default", '')
        doc_lines.append(f"\t:param {arg_name} ({arg_type}): {arg_anno}" + ('' if (default_value=='') else f"(optional, default={default_value})"))
        # doc_lines.append(f"\t:type {arg_name}: {arg_type}")
    doc_lines.append('\t"""')

    docstring = "\n".join(doc_lines)

    # Combine full function definition
    function_str = f"def {name}({params_str}):\n    {docstring}\n"
    return function_str


import shutil
import os

def clean_folder(folder_path: str):
    """
    Deletes all contents of the given folder without deleting the folder itself.

    Args:
        folder_path (str): Path to the folder to clean.

    Raises:
        FileNotFoundError: If the given folder_path does not exist.
        NotADirectoryError: If the given path is not a directory.
        PermissionError: If files/folders cannot be deleted due to permission issues.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"The folder '{folder_path}' does not exist.")
    if not os.path.isdir(folder_path):
        raise NotADirectoryError(f"The path '{folder_path}' is not a directory.")

    for entry in os.listdir(folder_path):
        entry_path = os.path.join(folder_path, entry)
        try:
            if os.path.isfile(entry_path) or os.path.islink(entry_path):
                os.remove(entry_path)  # remove file or symbolic link
            elif os.path.isdir(entry_path):
                shutil.rmtree(entry_path)  # remove directory recursively
        except Exception as e:
            print(f"Failed to delete '{entry_path}': {e}")
            

### @func: extract the bullets
def extract_bullets(text):
    """
    Extracts bullet points from a multiline string into a list.
    Assumes bullets start with '- ' at the beginning of a line (leading spaces allowed).
    
    Args:
        text (str): The input text containing bullet points.
        
    Returns:
        list[str]: A list of bullet point strings without the leading '- '.
    """
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('- '):
            bullets.append(line[2:].strip())
    return bullets


# Helper function to format argument lists (reusable)
def _format_args(args):
    arg_strs = []

    # Positional-only (Python 3.8+)
    posonlyargs = getattr(args, "posonlyargs", [])
    for arg in posonlyargs:
        arg_strs.append(arg.arg)

    # Regular args with defaults
    total_args = len(args.args)
    total_defaults = len(args.defaults)
    default_start = total_args - total_defaults
    for i, arg in enumerate(args.args):
        name = arg.arg
        if i >= default_start:
            default_val = args.defaults[i - default_start]
            default_code = ast.unparse(default_val) if hasattr(ast, "unparse") else "<default>"
            arg_strs.append(f"{name}={default_code}")
        else:
            arg_strs.append(name)

    # *args
    if args.vararg:
        arg_strs.append(f"*{args.vararg.arg}")
    elif args.kwonlyargs:
        arg_strs.append('*')  # bare * if no *args but kwonlyargs exist

    # Keyword-only args
    for i, arg in enumerate(args.kwonlyargs):
        name = arg.arg
        default_val = args.kw_defaults[i]
        if default_val is not None:
            default_code = ast.unparse(default_val) if hasattr(ast, "unparse") else "<default>"
            arg_strs.append(f"{name}={default_code}")
        else:
            arg_strs.append(name)

    # **kwargs
    if args.kwarg:
        arg_strs.append(f"**{args.kwarg.arg}")

    return arg_strs


def _format_with_line_numbers(lines, start_lineno, end_lineno):
    """Format lines with line numbers."""
    definition_lines = lines[start_lineno - 1:end_lineno]
    numbered_lines = [
        f"{i + start_lineno:4} | {line.rstrip()}"
        for i, line in enumerate(definition_lines)
    ]
    return '\n'.join(numbered_lines)


def _format_class_interface(class_node, class_name: str, all_lines):
    """Return only class attributes and method signatures (no bodies)."""
    attributes = []
    methods = []

    # Extract constructor to find attributes
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and item.name == '__init__':
            for stmt in item.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self':
                            attr_name = target.attr
                            if attr_name not in attributes:
                                attributes.append(attr_name)

    # Extract method signatures
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef):
            if item.name.startswith('__') and item.name.endswith('__') and item.name != '__init__':
                continue  # Skip special methods unless needed
            args = item.args
            arg_strs = []

            # Self is implied
            pos_offset = 1 if args.args and args.args[0].arg == 'self' else 0

            for arg in args.args[pos_offset:]:
                name = arg.arg
                if args.defaults:
                    idx = len(args.args) - len(args.defaults) - pos_offset
                    if args.args.index(arg) >= idx:
                        default = args.defaults[idx - (args.args.index(arg) - idx)]
                        def_str = ast.unparse(default) if hasattr(ast, 'unparse') else '<default>'
                        arg_strs.append(f"{name}={def_str}")
                    else:
                        arg_strs.append(name)
                else:
                    arg_strs.append(name)

            if args.vararg:
                arg_strs.append(f"*{args.vararg.arg}")
            if args.kwonlyargs:
                arg_strs.append('*')
                for kwarg in args.kwonlyargs:
                    name = kwarg.arg
                    if args.kw_defaults and args.kw_defaults[args.kwonlyargs.index(kwarg)] is not None:
                        default = args.kw_defaults[args.kwonlyargs.index(kwarg)]
                        def_str = ast.unparse(default) if hasattr(ast, 'unparse') else '<default>'
                        arg_strs.append(f"{name}={def_str}")
                    else:
                        arg_strs.append(name)
            if args.kwarg:
                arg_strs.append(f"**{args.kwarg.arg}")

            sig = f"{item.name}({', '.join(arg_strs)})"
            methods.append(sig)

    # Build output
    output = [f"📌 Class '{class_name}' Interface"]

    if attributes:
        output.append("  🔹 Attributes:")
        for attr in sorted(attributes):
            output.append(f"    • self.{attr}")

    if methods:
        output.append("  🔹 Methods:")
        for sig in sorted(methods):
            output.append(f"    • {sig}")

    if not attributes and not methods:
        output.append("  (No attributes or methods found)")

    return "\n".join(output)



def lint_python_file(filepath):
    """
    Run flake8 linter on the given Python file.
    
    Args:
        filepath (str): Path to the Python source file.
        
    Returns:
        str: Linter output or a message saying the file passed the linter.
    """
    try:
        # Run flake8 as a subprocess to capture stdout and stderr
        result = subprocess.run(
            ['flake8', filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        output = result.stdout.strip()
        error_output = result.stderr.strip()

        if error_output:
            # Some flake8 internal error or file access error
            return f"Error running linter:\n{error_output}"

        if output:
            # There were lint errors/warnings detected
            return output

        return "No linter errors found. The file is correct."

    except FileNotFoundError:
        return "flake8 is not installed or not found in PATH. Please install flake8."


def flatten_to_kv_string(data, parent_key='', sep='.'):
    lines = []
    
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            # Recursive calls for nested structures
            if isinstance(v, dict):
                res = flatten_to_kv_string(v, new_key, sep=sep)
                if res: lines.append(res)
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    res = flatten_to_kv_string(item, f"{new_key}[{i}]", sep=sep)
                    if res: lines.append(res)
            
            # The filter: check if value is not None and not an empty string
            elif v is not None and v != "":
                lines.append(f"{new_key}:\n{v}")
                
    return "\n\n".join(filter(None, lines))