#!/usr/bin/env python3
"""
Module Interchangeability Validator

A general and comprehensive tool to validate the interchangeability of two Python files
from the perspective of being imported as modules by other programs.

Usage:
    python module_interchangeability_validator.py <original_file.py> <test_file.py> [options]

Author: GitHub Copilot
Date: October 7, 2025
"""

import ast
import sys
import os
import importlib.util
import inspect
import difflib
import argparse
import types
import tempfile
import subprocess
import traceback
from typing import Dict, List, Set, Tuple, Any, Optional, Callable
from dataclasses import dataclass
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

@dataclass
class ModuleAnalysis:
    """Structure to store module analysis results"""
    filepath: str
    functions: Dict[str, Dict[str, Any]]
    classes: Dict[str, Dict[str, Any]]
    variables: Dict[str, Any]
    imports: Dict[str, Set[str]]
    decorators: Set[str]
    syntax_valid: bool
    importable: bool
    file_size: int
    line_count: int
    
class ModuleInterchangeabilityValidator:
    """Python module interchangeability validator"""
    
    def __init__(self, original_file: str, test_file: str, verbose: bool = False, run_differential: bool = False):
        self.original_file = original_file
        self.test_file = test_file
        self.verbose = verbose
        self.run_differential = run_differential
        self.original_analysis = None
        self.test_analysis = None
        self.differential_tester = DifferentialTester(self) if run_differential else None
        
    def log(self, message: str, level: str = "INFO"):
        """Logger with verbosity level"""
        if self.verbose or level in ["ERROR", "SUCCESS", "WARNING"]:
            prefix = {
                "INFO": "ℹ️",
                "SUCCESS": "✅",
                "ERROR": "❌",
                "WARNING": "⚠️",
                "DEBUG": "🔍"
            }.get(level, "ℹ️")
            print(f"{prefix} {message}")
    
    def analyze_file_structure(self, filepath: str) -> Optional[ModuleAnalysis]:
        """Analyze the complete structure of a Python file"""
        self.log(f"Structural analysis of {filepath}...", "DEBUG")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Syntax validation
            try:
                ast.parse(content)
                syntax_valid = True
                self.log(f"Python syntax valid for {filepath}", "SUCCESS")
            except SyntaxError as e:
                syntax_valid = False
                self.log(f"Syntax error in {filepath}: {e}", "ERROR")
                return None
            
            # AST analysis
            tree = ast.parse(content)
            
            functions = {}
            classes = {}
            variables = {}
            imports = {'from_imports': set(), 'direct_imports': set()}
            decorators = set()
            
            for node in ast.walk(tree):
                # Functions
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'defaults': len(node.args.defaults),
                        'varargs': node.args.vararg.arg if node.args.vararg else None,
                        'kwonlyargs': [arg.arg for arg in node.args.kwonlyargs],
                        'kwargs': node.args.kwarg.arg if node.args.kwarg else None,
                        'returns': ast.unparse(node.returns) if node.returns else None,
                        'docstring': ast.get_docstring(node),
                        'decorators': [ast.unparse(d) for d in node.decorator_list],
                        'is_async': isinstance(node, ast.AsyncFunctionDef)
                    }
                    functions[node.name] = func_info
                    
                    # Collect decorators
                    for decorator in node.decorator_list:
                        decorators.add(ast.unparse(decorator))
                
                # Classes
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'bases': [ast.unparse(base) for base in node.bases],
                        'methods': {},
                        'docstring': ast.get_docstring(node),
                        'decorators': [ast.unparse(d) for d in node.decorator_list]
                    }
                    
                    # Analyze class methods
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_info = {
                                'name': item.name,
                                'args': [arg.arg for arg in item.args.args],
                                'is_async': isinstance(item, ast.AsyncFunctionDef),
                                'docstring': ast.get_docstring(item)
                            }
                            class_info['methods'][item.name] = method_info
                    
                    classes[node.name] = class_info
                
                # Imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports['direct_imports'].add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports['from_imports'].add(f"{module}.{alias.name}")
                
                # Global variables (module-level assignments)
                elif isinstance(node, ast.Assign):
                    # Check if we are at the module level by walking the parents
                    is_module_level = True
                    for parent in ast.walk(tree):
                        if hasattr(parent, 'body') and node not in parent.body:
                            if not isinstance(parent, ast.Module):
                                is_module_level = False
                                break
                    
                    if is_module_level:
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                try:
                                    value = ast.unparse(node.value)
                                    variables[target.id] = {
                                        'value': value,
                                        'line': node.lineno,
                                        'type': type(node.value).__name__
                                    }
                                except:
                                    variables[target.id] = {
                                        'value': '<complex_expression>',
                                        'line': node.lineno,
                                        'type': 'complex'
                                    }
            
            # File statistics
            file_size = os.path.getsize(filepath)
            line_count = len(content.split('\n'))
            
            # Importability test
            importable = self.test_importability(filepath)
            
            return ModuleAnalysis(
                filepath=filepath,
                functions=functions,
                classes=classes,
                variables=variables,
                imports=imports,
                decorators=decorators,
                syntax_valid=syntax_valid,
                importable=importable,
                file_size=file_size,
                line_count=line_count
            )
            
        except Exception as e:
            self.log(f"Error analyzing {filepath}: {e}", "ERROR")
            return None
    
    def test_importability(self, filepath: str) -> bool:
        """Test if a file can be imported as a module"""
        try:
            # Create a temporary module name
            module_name = os.path.basename(filepath).replace('.py', '_temp')
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # Try to load the module without fully executing it
                spec.loader.exec_module(module)
                return True
            return False
        except Exception as e:
            self.log(f"Import error for {filepath}: {e}", "DEBUG")
            return False
    
    def analyze_signatures_compatibility(self) -> Dict[str, Any]:
        """Analyze the compatibility of function signatures"""
        self.log("Analyzing signature compatibility...", "INFO")
        
        results = {
            'compatible_functions': [],
            'incompatible_functions': [],
            'missing_functions': [],
            'extra_functions': [],
            'signature_differences': {}
        }
        
        orig_funcs = self.original_analysis.functions
        test_funcs = self.test_analysis.functions
        
        # Functions missing in the test
        for func_name in orig_funcs:
            if func_name not in test_funcs:
                results['missing_functions'].append(func_name)
        
        # Extra functions in the test
        for func_name in test_funcs:
            if func_name not in orig_funcs:
                results['extra_functions'].append(func_name)
        
        # Compare signatures for common functions
        common_functions = set(orig_funcs.keys()) & set(test_funcs.keys())
        
        for func_name in common_functions:
            orig_func = orig_funcs[func_name]
            test_func = test_funcs[func_name]
            
            signature_diff = []
            
            # Compare arguments
            if orig_func['args'] != test_func['args']:
                signature_diff.append(f"Arguments: {orig_func['args']} -> {test_func['args']}")
            
            # Compare default arguments
            if orig_func['defaults'] != test_func['defaults']:
                signature_diff.append(f"Defaults: {orig_func['defaults']} -> {test_func['defaults']}")
            
            # Compare *args
            if orig_func['varargs'] != test_func['varargs']:
                signature_diff.append(f"*args: {orig_func['varargs']} -> {test_func['varargs']}")
            
            # Compare **kwargs
            if orig_func['kwargs'] != test_func['kwargs']:
                signature_diff.append(f"**kwargs: {orig_func['kwargs']} -> {test_func['kwargs']}")
            
            # Compare return type
            if orig_func['returns'] != test_func['returns']:
                signature_diff.append(f"Return: {orig_func['returns']} -> {test_func['returns']}")
            
            # Compare async/sync
            if orig_func['is_async'] != test_func['is_async']:
                signature_diff.append(f"Async: {orig_func['is_async']} -> {test_func['is_async']}")
            
            if signature_diff:
                results['incompatible_functions'].append(func_name)
                results['signature_differences'][func_name] = signature_diff
            else:
                results['compatible_functions'].append(func_name)
        
        return results
    
    def analyze_classes_compatibility(self) -> Dict[str, Any]:
        """Analyze the compatibility of classes"""
        self.log("Analyzing class compatibility...", "INFO")
        
        results = {
            'compatible_classes': [],
            'incompatible_classes': [],
            'missing_classes': [],
            'extra_classes': [],
            'class_differences': {}
        }
        
        orig_classes = self.original_analysis.classes
        test_classes = self.test_analysis.classes
        
        # Missing classes
        for class_name in orig_classes:
            if class_name not in test_classes:
                results['missing_classes'].append(class_name)
        
        # Extra classes
        for class_name in test_classes:
            if class_name not in orig_classes:
                results['extra_classes'].append(class_name)
        
        # Compare common classes
        common_classes = set(orig_classes.keys()) & set(test_classes.keys())
        
        for class_name in common_classes:
            orig_class = orig_classes[class_name]
            test_class = test_classes[class_name]
            
            class_diff = []
            
            # Compare base classes
            if orig_class['bases'] != test_class['bases']:
                class_diff.append(f"Bases: {orig_class['bases']} -> {test_class['bases']}")
            
            # Compare methods
            orig_methods = set(orig_class['methods'].keys())
            test_methods = set(test_class['methods'].keys())
            
            missing_methods = orig_methods - test_methods
            extra_methods = test_methods - orig_methods
            
            if missing_methods:
                class_diff.append(f"Missing methods: {list(missing_methods)}")
            if extra_methods:
                class_diff.append(f"Extra methods: {list(extra_methods)}")
            
            # Compare signatures of common methods
            common_methods = orig_methods & test_methods
            for method_name in common_methods:
                orig_method = orig_class['methods'][method_name]
                test_method = test_class['methods'][method_name]
                
                if orig_method['args'] != test_method['args']:
                    class_diff.append(f"Method {method_name}: {orig_method['args']} -> {test_method['args']}")
            
            if class_diff:
                results['incompatible_classes'].append(class_name)
                results['class_differences'][class_name] = class_diff
            else:
                results['compatible_classes'].append(class_name)
        
        return results
    
    def analyze_variables_compatibility(self) -> Dict[str, Any]:
        """Analyze the compatibility of global variables"""
        self.log("Analyzing global variables compatibility...", "INFO")
        
        orig_vars = self.original_analysis.variables
        test_vars = self.test_analysis.variables
        
        results = {
            'compatible_variables': [],
            'missing_variables': [],
            'extra_variables': [],
            'different_variables': []
        }
        
        # Missing variables
        for var_name in orig_vars:
            if var_name not in test_vars:
                results['missing_variables'].append(var_name)
        
        # Extra variables
        for var_name in test_vars:
            if var_name not in orig_vars:
                results['extra_variables'].append(var_name)
        
        # Variables with different values
        common_vars = set(orig_vars.keys()) & set(test_vars.keys())
        for var_name in common_vars:
            if orig_vars[var_name]['value'] != test_vars[var_name]['value']:
                results['different_variables'].append({
                    'name': var_name,
                    'original': orig_vars[var_name]['value'],
                    'test': test_vars[var_name]['value']
                })
            else:
                results['compatible_variables'].append(var_name)
        
        return results
    
    def analyze_imports_compatibility(self) -> Dict[str, Any]:
        """Analyze the compatibility of imports"""
        self.log("Analyzing imports compatibility...", "INFO")
        
        orig_imports = self.original_analysis.imports
        test_imports = self.test_analysis.imports
        
        results = {
            'missing_direct_imports': list(orig_imports['direct_imports'] - test_imports['direct_imports']),
            'extra_direct_imports': list(test_imports['direct_imports'] - orig_imports['direct_imports']),
            'missing_from_imports': list(orig_imports['from_imports'] - test_imports['from_imports']),
            'extra_from_imports': list(test_imports['from_imports'] - orig_imports['from_imports']),
            'compatible_imports': len(set(orig_imports['direct_imports']) & set(test_imports['direct_imports'])) + 
                              len(set(orig_imports['from_imports']) & set(test_imports['from_imports']))
        };
        
        return results
    
    def calculate_compatibility_score(self) -> float:
        """Calculate an overall compatibility score (0-100)"""
        self.log("Calculating overall compatibility score...", "INFO")
        
        total_elements = 0
        compatible_elements = 0
        
        # Functions
        total_elements += len(self.original_analysis.functions)
        sig_analysis = self.analyze_signatures_compatibility()
        compatible_elements += len(sig_analysis['compatible_functions'])
        
        # Classes
        total_elements += len(self.original_analysis.classes)
        class_analysis = self.analyze_classes_compatibility()
        compatible_elements += len(class_analysis['compatible_classes'])
        
        # Variables
        total_elements += len(self.original_analysis.variables)
        var_analysis = self.analyze_variables_compatibility()
        compatible_elements += len(var_analysis['compatible_variables'])
        
        if total_elements == 0:
            return 100.0
        
        return (compatible_elements / total_elements) * 100
    
    def _get_current_date(self) -> str:
        """Get the current date and time formatted"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def validate(self) -> bool:
        """Main validation method"""
        self.log("🚀 Starting interchangeability validation...", "INFO")
        
        # Analyze both files
        self.original_analysis = self.analyze_file_structure(self.original_file)
        self.test_analysis = self.analyze_file_structure(self.test_file)
        
        if not self.original_analysis:
            self.log(f"Unable to analyze original file: {self.original_file}", "ERROR")
            return False
        
        if not self.test_analysis:
            self.log(f"Unable to analyze test file: {self.test_file}", "ERROR")
            return False
        
        # Run differential tests if requested
        if self.run_differential and self.differential_tester:
            self.differential_tester.run_differential_tests()
        
        # Calculate final score
        score = self.calculate_compatibility_score()
        is_interchangeable = score >= 85
        
        # Adjust score based on differential tests if available
        if self.run_differential and self.differential_tester and self.differential_tester.test_results:
            total_diff_tests = len(self.differential_tester.test_results)
            passed_diff_tests = sum(1 for r in self.differential_tester.test_results if r.passed)
            
            if total_diff_tests > 0:
                diff_score = (passed_diff_tests / total_diff_tests) * 100
                # Weight the scores: 70% static analysis, 30% differential testing
                final_score = (score * 0.7) + (diff_score * 0.3)
                score = final_score
                is_interchangeable = score >= 85
                
                self.log(f"🧪 Differential tests: {passed_diff_tests}/{total_diff_tests} passed", "INFO")
        
        self.log(f"🎯 Final score: {score:.1f}/100", "SUCCESS" if is_interchangeable else "WARNING")
        self.log(f"🔄 Interchangeability: {'✅ VALIDATED' if is_interchangeable else '❌ NOT VALIDATED'}", 
                "SUCCESS" if is_interchangeable else "ERROR")
        
        return is_interchangeable

    def generate_detailed_report(self) -> str:
        """Generate a detailed compatibility report"""
        report = []
        report.append("=" * 80)
        report.append("🔍 MODULE INTERCHANGEABILITY REPORT")
        report.append("=" * 80)
        report.append(f"Original file: {self.original_file}")
        report.append(f"Test file: {self.test_file}")
        report.append(f"Date: {self._get_current_date()}")
        report.append("")
        
        # Check if analyses are available
        if not self.original_analysis or not self.test_analysis:
            report.append("❌ ERROR: Could not analyze one or both files")
            if not self.original_analysis:
                report.append(f"  - Failed to analyze original file: {self.original_file}")
            if not self.test_analysis:
                report.append(f"  - Failed to analyze test file: {self.test_file}")
            report.append("=" * 80)
            return "\n".join(report)
        
        # Basic statistics
        report.append("📊 BASIC STATISTICS")
        report.append("-" * 40)
        report.append(f"Original - Size: {self.original_analysis.file_size:,} bytes, Lines: {self.original_analysis.line_count}")
        report.append(f"Test - Size: {self.test_analysis.file_size:,} bytes, Lines: {self.test_analysis.line_count}")
        
        if self.original_analysis.file_size > 0:
            size_reduction = ((self.original_analysis.file_size - self.test_analysis.file_size) / self.original_analysis.file_size) * 100
            report.append(f"Size reduction: {size_reduction:.1f}%")
        
        report.append(f"Original - Syntax: {'✅' if self.original_analysis.syntax_valid else '❌'}, Importable: {'✅' if self.original_analysis.importable else '❌'}")
        report.append(f"Test - Syntax: {'✅' if self.test_analysis.syntax_valid else '❌'}, Importable: {'✅' if self.test_analysis.importable else '❌'}")
        report.append("")
        
        # Compatibility score
        score = self.calculate_compatibility_score()
        report.append("🎯 COMPATIBILITY SCORE")
        report.append("-" * 40)
        report.append(f"Global score: {score:.1f}/100")
        
        if score >= 95:
            report.append("🟢 EXCELLENT - Modules are interchangeable")
        elif score >= 85:
            report.append("🟡 GOOD - Modules are largely interchangeable with minor differences")
        elif score >= 70:
            report.append("🟠 AVERAGE - Modules are partially interchangeable")
        else:
            report.append("🔴 LOW - Modules are not interchangeable")
        report.append("")
        
        # Functions analysis
        sig_analysis = self.analyze_signatures_compatibility()
        report.append("🔧 FUNCTIONS ANALYSIS")
        report.append("-" * 40)
        report.append(f"Original: {len(self.original_analysis.functions)} functions")
        report.append(f"Test: {len(self.test_analysis.functions)} functions")
        report.append(f"✅ Compatible: {len(sig_analysis['compatible_functions'])}")
        report.append(f"❌ Incompatible: {len(sig_analysis['incompatible_functions'])}")
        report.append(f"⚠️ Missing: {len(sig_analysis['missing_functions'])}")
        report.append(f"➕ Extra: {len(sig_analysis['extra_functions'])}")
        
        if sig_analysis['missing_functions']:
            report.append("\nMissing functions:")
            for func in sig_analysis['missing_functions']:
                report.append(f"  - {func}")
        
        if sig_analysis['extra_functions']:
            report.append("\nExtra functions:")
            for func in sig_analysis['extra_functions']:
                report.append(f"  + {func}")
        
        if sig_analysis['incompatible_functions']:
            report.append("\nIncompatible functions:")
            for func in sig_analysis['incompatible_functions']:
                report.append(f"  ❌ {func}:")
                for diff in sig_analysis['signature_differences'][func]:
                    report.append(f"    - {diff}")
        
        report.append("")
        
        # Classes analysis
        class_analysis = self.analyze_classes_compatibility()
        report.append("🏗️ CLASSES ANALYSIS")
        report.append("-" * 40)
        report.append(f"Original: {len(self.original_analysis.classes)} classes")
        report.append(f"Test: {len(self.test_analysis.classes)} classes")
        report.append(f"✅ Compatible: {len(class_analysis['compatible_classes'])}")
        report.append(f"❌ Incompatible: {len(class_analysis['incompatible_classes'])}")
        report.append(f"⚠️ Missing: {len(class_analysis['missing_classes'])}")
        report.append(f"➕ Extra: {len(class_analysis['extra_classes'])}")
        
        if class_analysis['missing_classes']:
            report.append("\nMissing classes:")
            for cls in class_analysis['missing_classes']:
                report.append(f"  - {cls}")
        
        if class_analysis['extra_classes']:
            report.append("\nExtra classes:")
            for cls in class_analysis['extra_classes']:
                report.append(f"  + {cls}")
        
        report.append("")
        
        # Variables analysis
        var_analysis = self.analyze_variables_compatibility()
        report.append("📝 GLOBAL VARIABLES ANALYSIS")
        report.append("-" * 40)
        report.append(f"Original: {len(self.original_analysis.variables)} variables")
        report.append(f"Test: {len(self.test_analysis.variables)} variables")
        report.append(f"✅ Compatible: {len(var_analysis['compatible_variables'])}")
        report.append(f"⚠️ Missing: {len(var_analysis['missing_variables'])}")
        report.append(f"➕ Extra: {len(var_analysis['extra_variables'])}")
        report.append(f"🔄 Different: {len(var_analysis['different_variables'])}")
        
        if var_analysis['different_variables']:
            report.append("\nVariables with different values:")
            for var in var_analysis['different_variables']:
                report.append(f"  🔄 {var['name']}: {var['original']} -> {var['test']}")
        
        report.append("")
        
        # Imports analysis
        import_analysis = self.analyze_imports_compatibility()
        report.append("📦 IMPORTS ANALYSIS")
        report.append("-" * 40)
        report.append(f"✅ Compatible imports: {import_analysis['compatible_imports']}")
        report.append(f"⚠️ Missing direct imports: {len(import_analysis['missing_direct_imports'])}")
        report.append(f"➕ Extra direct imports: {len(import_analysis['extra_direct_imports'])}")
        report.append(f"⚠️ Missing from imports: {len(import_analysis['missing_from_imports'])}")
        report.append(f"➕ Extra from imports: {len(import_analysis['extra_from_imports'])}")
        
        if import_analysis['missing_direct_imports']:
            report.append("\nMissing direct imports:")
            for imp in import_analysis['missing_direct_imports']:
                report.append(f"  - {imp}")
        
        if import_analysis['extra_direct_imports']:
            report.append("\nExtra direct imports:")
            for imp in import_analysis['extra_direct_imports']:
                report.append(f"  + {imp}")
        
        # Differential testing results
        if self.run_differential and self.differential_tester and self.differential_tester.test_results:
            diff_report = self.differential_tester.generate_differential_report()
            report.append(diff_report)
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)

@dataclass
class DifferentialTestResult:
    """Structure to store differential test results"""
    test_name: str
    function_name: str
    original_result: Any
    test_result: Any
    passed: bool
    error_msg: Optional[str] = None
    execution_time_original: float = 0.0
    execution_time_test: float = 0.0

class DifferentialTester:
    """Differential testing for module behavior validation"""
    
    def __init__(self, validator: 'ModuleInterchangeabilityValidator'):
        self.validator = validator
        self.test_results: List[DifferentialTestResult] = []
        
    def create_safe_test_environment(self) -> Dict[str, Any]:
        """Create a safe environment for testing functions"""
        safe_env = {
            # Built-in functions
            '__builtins__': {
                '__import__': __import__,
                'print': lambda *args, **kwargs: None,  # Suppress print
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'list': list,
                'dict': dict,
                'tuple': tuple,
                'set': set,
                'range': range,
                'enumerate': enumerate,
                'zip': zip,
                'min': min,
                'max': max,
                'sum': sum,
                'abs': abs,
                'round': round,
                'isinstance': isinstance,
                'type': type,
                'hasattr': hasattr,
                'getattr': getattr,
                'setattr': setattr,
                'delattr': delattr,
            },
            # Common modules
            'math': __import__('math'),
            'random': __import__('random'),
            'datetime': __import__('datetime'),
            're': __import__('re'),
            'json': __import__('json'),
            'os': __import__('os'),
            'sys': __import__('sys'),
            'time': __import__('time'),
            'threading': __import__('threading'),
            'queue': __import__('queue'),
            'io': __import__('io'),
            'signal': __import__('signal'),
            'warnings': __import__('warnings'),
        }
        return safe_env
    
    def load_module_safely(self, filepath: str) -> Optional[types.ModuleType]:
        """Load a module in a safe environment"""
        try:
            module_name = os.path.basename(filepath).replace('.py', '_test')
            
            # Read the source code directly
            with open(filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # Create a safe environment
            safe_env = self.create_safe_test_environment()
            safe_env['__name__'] = module_name
            safe_env['__file__'] = filepath
            
            # Execute the module in safe environment
            exec(source_code, safe_env)
            
            # Create a module object
            module = types.ModuleType(module_name)
            module.__file__ = filepath
            
            # Copy safe attributes to module
            for name, obj in safe_env.items():
                if not name.startswith('__') or name in ['__name__', '__file__']:
                    setattr(module, name, obj)
            
            return module
        except Exception as e:
            self.validator.log(f"Error loading module {filepath}: {e}", "DEBUG")
        return None
    
    def create_test_inputs(self, func_signature: Dict[str, Any]) -> List[Tuple[List, Dict]]:
        """Create test input combinations for a function"""
        test_cases = []
        
        args = func_signature.get('args', [])
        
        # Generate test cases based on argument types
        if len(args) == 0:
            # No arguments - single call with empty args
            test_cases.append(([], {}))
        elif len(args) <= 3:
            # Small number of arguments - generate combinations
            basic_values = [
                [],                    # Empty list
                [1, 2, 3],            # List of numbers
                ["hello", "world"],   # List of strings
                [{"key": "value"}],    # List of dicts
            ]
            
            for i, value_set in enumerate(basic_values[:len(args) + 1]):
                test_args = value_set[:len(args)]
                test_cases.append((test_args, {}))
        else:
            # Many arguments - use minimal test
            test_cases.append(([None] * len(args), {}))
        
        return test_cases
    
    def execute_function_safely(self, func: Callable, args: List, kwargs: Dict) -> Tuple[Any, float, Optional[str]]:
        """Execute a function safely and return result, time, and error"""
        import time
        import signal
        start_time = time.time()
        
        try:
            # Set timeout for execution
            def timeout_handler(signum, frame):
                raise TimeoutError("Function execution timeout")
            
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)  # 5 second timeout
            
            result = func(*args, **kwargs)
            
            signal.alarm(0)  # Cancel timeout
            
            execution_time = time.time() - start_time
            return result, execution_time, None
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}"
            return None, execution_time, error_msg
        finally:
            try:
                signal.alarm(0)  # Cancel timeout
            except:
                pass
    
    def compare_results(self, result1: Any, result2: Any) -> bool:
        """Compare two results for equality"""
        try:
            # Direct comparison
            if result1 == result2:
                return True
            
            # Type comparison
            if type(result1) != type(result2):
                return False
            
            # For collections, compare elements
            if isinstance(result1, (list, tuple)):
                if len(result1) != len(result2):
                    return False
                return all(self.compare_results(r1, r2) for r1, r2 in zip(result1, result2))
            
            elif isinstance(result1, dict):
                if set(result1.keys()) != set(result2.keys()):
                    return False
                return all(self.compare_results(result1[k], result2[k]) for k in result1.keys())
            
            # String comparison with normalization
            elif isinstance(result1, str):
                return result1.strip() == result2.strip()
            
            return False
            
        except Exception:
            return False
    
    def test_function_differentially(self, func_name: str) -> List[DifferentialTestResult]:
        """Test a function differentially between original and test modules"""
        results = []
        
        if not self.validator.original_analysis or not self.validator.test_analysis:
            return results
        
        orig_funcs = self.validator.original_analysis.functions
        test_funcs = self.validator.test_analysis.functions
        
        if func_name not in orig_funcs or func_name not in test_funcs:
            return results
        
        # Load modules safely
        orig_module = self.load_module_safely(self.validator.original_file)
        test_module = self.load_module_safely(self.validator.test_file)
        
        if not orig_module or not test_module:
            return results
        
        # Get functions
        orig_func = getattr(orig_module, func_name, None)
        test_func = getattr(test_module, func_name, None)
        
        if not orig_func or not test_func:
            return results
        
        # Create test inputs
        func_signature = orig_funcs[func_name]
        test_cases = self.create_test_inputs(func_signature)
        
        for i, (args, kwargs) in enumerate(test_cases):
            test_name = f"{func_name}_test_{i+1}"
            
            # Execute original function
            orig_result, orig_time, orig_error = self.execute_function_safely(orig_func, args, kwargs)
            
            # Execute test function
            test_result, test_time, test_error = self.execute_function_safely(test_func, args, kwargs)
            
            # Compare results
            if orig_error or test_error:
                # Both should have the same error type
                passed = (orig_error is not None and test_error is not None and 
                         type(orig_error.split(':')[0]) == type(test_error.split(':')[0]))
                error_msg = f"Original: {orig_error}, Test: {test_error}" if not passed else None
            else:
                passed = self.compare_results(orig_result, test_result)
                error_msg = None
            
            result = DifferentialTestResult(
                test_name=test_name,
                function_name=func_name,
                original_result=orig_result,
                test_result=test_result,
                passed=passed,
                error_msg=error_msg,
                execution_time_original=orig_time,
                execution_time_test=test_time
            )
            
            results.append(result)
        
        return results
    
    def run_differential_tests(self, max_functions_per_module: int = 10) -> List[DifferentialTestResult]:
        """Run differential tests on compatible functions"""
        self.validator.log("Running differential tests...", "INFO")
        
        all_results = []
        
        if not self.validator.original_analysis or not self.validator.test_analysis:
            self.validator.log("Cannot run differential tests: missing module analysis", "WARNING")
            return all_results
        
        orig_funcs = self.validator.original_analysis.functions
        test_funcs = self.validator.test_analysis.functions
        
        # Find common functions
        common_functions = set(orig_funcs.keys()) & set(test_funcs.keys())
        
        # Limit the number of functions to test
        test_functions = list(common_functions)[:max_functions_per_module]
        
        for func_name in test_functions:
            self.validator.log(f"Testing function: {func_name}", "DEBUG")
            
            try:
                results = self.test_function_differentially(func_name)
                all_results.extend(results)
            except Exception as e:
                self.validator.log(f"Error testing function {func_name}: {e}", "DEBUG")
        
        self.test_results = all_results
        return all_results
    
    def generate_differential_report(self) -> str:
        """Generate a differential test report"""
        if not self.test_results:
            return "No differential tests performed."
        
        report = []
        report.append("")
        report.append("🧪 DIFFERENTIAL TESTING RESULTS")
        report.append("-" * 40)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.passed)
        failed_tests = total_tests - passed_tests
        
        report.append(f"Total tests: {total_tests}")
        report.append(f"✅ Passed: {passed_tests}")
        report.append(f"❌ Failed: {failed_tests}")
        report.append(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
        report.append("")
        
        # Group results by function
        results_by_function = {}
        for result in self.test_results:
            if result.function_name not in results_by_function:
                results_by_function[result.function_name] = []
            results_by_function[result.function_name].append(result)
        
        for func_name, results in results_by_function.items():
            func_passed = sum(1 for r in results if r.passed)
            func_total = len(results)
            
            report.append(f"🔧 {func_name}: {func_passed}/{func_total} tests passed")
            
            # Show failed tests
            failed_results = [r for r in results if not r.passed]
            for result in failed_results:
                report.append(f"  ❌ {result.test_name}")
                if result.error_msg:
                    report.append(f"     Error: {result.error_msg}")
                else:
                    report.append(f"     Original: {result.original_result}")
                    report.append(f"     Test: {result.test_result}")
            
            report.append("")
        
        return "\n".join(report)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Python module interchangeability validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  python module_interchangeability_validator.py original.py test.py
  python module_interchangeability_validator.py original.py test.py --verbose
  python module_interchangeability_validator.py original.py test.py --output report.txt
        """
    )
    
    parser.add_argument('original', help='Original reference Python file')
    parser.add_argument('test', help='Python file to test')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose mode for debugging')
    parser.add_argument('--output', '-o', 
                       help='Output file for the report (optional)')
    parser.add_argument('--score-only', '-s', action='store_true',
                       help='Display only the compatibility score')
    parser.add_argument('--differential', '-d', action='store_true',
                       help='Run differential behavioral tests for more realistic validation')
    
    args = parser.parse_args()
    
    # Check that files exist
    if not os.path.exists(args.original):
        print(f"❌ Original file does not exist: {args.original}")
        sys.exit(1)
    
    if not os.path.exists(args.test):
        print(f"❌ Test file does not exist: {args.test}")
        sys.exit(1)
    
    # Create the validator
    validator = ModuleInterchangeabilityValidator(
        original_file=args.original,
        test_file=args.test,
        verbose=args.verbose,
        run_differential=args.differential
    )
    
    # Run the validation
    is_interchangeable = validator.validate()
    
    # Display the score if requested
    if args.score_only:
        score = validator.calculate_compatibility_score()
        print(f"{score:.1f}")
    else:
        # Generate the report
        report = validator.generate_detailed_report()
        
        # Display the report
        print(report)
        
        # Save to a file if requested
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(report)
                print(f"\n📄 Report saved to: {args.output}")
            except Exception as e:
                print(f"❌ Error saving report: {e}")
    
    # Exit code
    sys.exit(0 if is_interchangeable else 1)

if __name__ == "__main__":
    main()