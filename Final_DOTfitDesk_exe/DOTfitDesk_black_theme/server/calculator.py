from sympy import sympify, N
from sympy.core.sympify import SympifyError
import numpy as np
import statistics
import math
import mpmath
import re

def register(mcp):
    PRECISION = 200

    def manual_mean(values):
        evaluated = []
        # If values is just a single number (not a list), handle it
        if not isinstance(values, (list, tuple)):
            values = [values]
            
        for v in values:
            try:
                evaluated.append(float(N(sympify(v), PRECISION)))
            except Exception:
                evaluated.append(float(v))
        total = 0.0
        count = 0
        for x in evaluated:
            total += x
            count += 1
        return total / count if count > 0 else 0

    SAFE_ENV = {
        "np": np,
        "math": math,
        "mpmath": mpmath,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "log": math.log, "log10": math.log10, "ln": math.log,
        "exp": math.exp, "sqrt": math.sqrt, "abs": abs,
        "mean": manual_mean,
        "median": statistics.median,
        "variance": statistics.variance,
        "stdev": statistics.stdev,
        "sum": sum, "max": max, "min": min,
    }

    def convert_stats(expr: str) -> str:
        functions = ["mean", "stdev", "variance", "median"]
        pattern = r'\b(' + "|".join(functions) + r')\s*\('
        i = 0
        while True:
            match = re.search(pattern, expr[i:])
            if not match:
                break
            fn = match.group(1)
            start = match.start() + i + len(fn) + 1
            depth = 0
            for j in range(start, len(expr)):
                if expr[j] == "(":
                    depth += 1
                elif expr[j] == ")":
                    if depth == 0:
                        end = j
                        break
                    depth -= 1
            args = expr[start:end].strip()
            if not (args.startswith("[") and args.endswith("]")):
                expr = expr[:start] + "[" + args + "]" + expr[end:]
            i = end + 1
        return expr

    def format_result(value):
        try:
            f = float(value)
            if f.is_integer():
                return format(int(f), ",")
            if abs(f) < 1e-5 or abs(f) > 1e8:
                return f"{f:.4e}"
            formatted = f"{f:.4f}"
            left, right = formatted.split(".")
            left = format(int(left), ",")
            return f"{left}.{right}"
        except Exception:
            return "input not in valid mathematical format"

    # ========================================================
    # 🆕 NEW FUNCTION: Smart Comma Remover
    # ========================================================
    def sanitize_input(expr: str) -> str:
        """
        Removes commas from numbers (e.g. '1,000' -> '1000')
        BUT keeps commas inside function calls (e.g. 'max(1, 2)').
        """
        new_expr = []
        depth = 0  # Tracks if we are inside parentheses ()
        
        for char in expr:
            if char in "([{":
                depth += 1
                new_expr.append(char)
            elif char in ")]}":
                depth -= 1
                new_expr.append(char)
            elif char == ",":
                if depth > 0:
                    # Inside a function like mean(1, 2) -> Keep the comma
                    new_expr.append(char)
                else:
                    # Outside a function (e.g. 1,000) -> Skip the comma
                    pass 
            else:
                new_expr.append(char)
                
        return "".join(new_expr)

    def calculate(expr: str) -> str:
        if not isinstance(expr, str) or expr.strip() == "":
            return "input not in valid mathematical format"

        # 1. First, remove commas from numbers
        expr = sanitize_input(expr)
        
        # 2. Handle powers
        expr = expr.replace("^", "**")
        
        # 3. Handle statistical functions
        expr = convert_stats(expr)

        try:
            value = N(sympify(expr, locals=SAFE_ENV), PRECISION)
        except ZeroDivisionError:
            return "division by zero"
        except SympifyError:
            return "input not in valid mathematical format"
        except Exception as e:
            return f"Error: {str(e)}"

        return format_result(value)

    @mcp.tool()
    async def calculate_math(expression: str) -> str:
        result = calculate(expression)
        return (f"🔢 Calculation\n"
                f"────────────────────\n"
                f"📥 Input: {expression}\n"
                f"📤 Output: {result}"
                )
    return calculate_math