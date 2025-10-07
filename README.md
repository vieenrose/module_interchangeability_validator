# Module Interchangeability Validator

## 🎯 Description

The **Module Interchangeability Validator** is a comprehensive and general-purpose tool for checking the interchangeability of two Python files from the perspective of being imported as modules by other programs.

## 🚀 Installation

No installation required. The tool uses only Python standard libraries:
- `ast` (Syntactic analysis)
- `sys`, `os`, `argparse` (System interface and CLI)
- `inspect`, `difflib`, `typing` (Analysis and comparison)
- `dataclasses` (Data structures)
- `warnings` (Warning management)

## 📋 Usage

### Basic syntax

```bash
python module_interchangeability_validator.py <original_file.py> <test_file.py> [options]
```

### Available options

- `--verbose, -v` : Verbose mode for debugging
- `--output, -o <file>` : Save report to a file
- `--score-only, -s` : Display only the compatibility score

### Usage examples

#### 1. Simple validation with score
```bash
python module_interchangeability_validator.py original.py test.py --score-only
```

#### 2. Complete validation with detailed report
```bash
python module_interchangeability_validator.py original.py test.py --verbose
```

#### 3. Validation with report saving
```bash
python module_interchangeability_validator.py original.py test.py --output report.txt
```

#### 4. Silent validation (score only)
```bash
python module_interchangeability_validator.py original.py test.py -s
```

## 📊 Understanding the results

### Compatibility score (0-100)

- **🟢 95-100** : EXCELLENT - The modules are perfectly interchangeable
- **🟡 85-94** : GOOD - The modules are largely interchangeable with minor differences
- **🟠 70-84** : AVERAGE - The modules are partially interchangeable
- **🔴 0-69** : POOR - The modules are not interchangeable

### Analyses performed

#### 1. **Structural analysis**
- Validation of Python syntax
- Importability test
- Line counting and file size

#### 2. **Function analysis**
- **Compatible** : Same signatures (arguments, return, decorators)
- **Incompatible** : Differences in signatures
- **Missing** : Present in the original, absent in the test
- **Additional** : Absent in the original, present in the test

#### 3. **Class analysis**
- Inheritance and base classes
- Methods and their signatures
- Class decorators

#### 4. **Global variable analysis**
- Variables defined at the module level
- Values and types of variables

#### 5. **Import analysis**
- Direct imports (`import module`)
- From imports (`from module import name`)
- Dependency compatibility

## 🔧 Advanced features

### Automatic incompatibility detection

The tool automatically detects:

1. **Renamed arguments** : `func(arg1)` vs `func(arg_1)`
2. **Different return types** : `-> str` vs `-> int`
3. **Default parameters** : `func(a=1)` vs `func(a=2)`
4. **Variable arguments** : `*args`, `**kwargs`
5. **Async functions** : `async def` vs `def`
6. **Different base classes** : `class A(B)` vs `class A(C)`
7. **Missing or additional methods**

### Error handling

The tool gracefully handles:
- Non-existent files
- Syntax errors
- Missing imports
- Unresolved external dependencies

## 📈 Calculated metrics

### Size reduction
```python
reduction = ((original_size - test_size) / original_size) * 100
```

### Compatibility score
```python
score = (compatible_elements / total_elements) * 100
```

The elements include:
- Functions with identical signatures
- Classes with identical methods
- Global variables with the same values
- Compatible imports

## 🎯 Typical use cases

### 1. Code optimization
Check that an optimized version remains compatible:
```bash
python module_interchangeability_validator.py original_module.py optimized_module.py
```

### 2. Refactoring
Validate that a refactoring hasn't broken the API:
```bash
python module_interchangeability_validator.py pre_refactor.py post_refactor.py
```

### 3. Dependency updates
Check compatibility after an update:
```bash
python module_interchangeability_validator.py old_version.py new_version.py
```

### 4. Regression testing
Integrate into CI/CD:
```bash
python module_interchangeability_validator.py reference.py candidate.py --score-only
```

## 📋 Sample report

```
================================================================================
🔍 MODULE INTERCHANGEABILITY REPORT
================================================================================
Original file: src/common_original_backup.py
Test file: src/common.py
Date: 2025-10-07 15:03:34

📊 BASIC STATISTICS
----------------------------------------
Original - Size: 208,259 bytes, Lines: 3582
Test - Size: 47,504 bytes, Lines: 1361
Size reduction: 77.2%
Original - Syntax: ✅, Importable: ❌
Test - Syntax: ✅, Importable: ❌

🎯 COMPATIBILITY SCORE
----------------------------------------
Overall score: 16.4/100
🔴 POOR - The modules are not interchangeable

🔧 FUNCTION ANALYSIS
----------------------------------------
Original: 70 functions
Test: 74 functions
✅ Compatible: 11
❌ Incompatible: 59
⚠️ Missing: 0
➕ Additional: 4

Incompatible functions:
  ❌ waiting_rasa_queue:
    - Arguments: ['rasa_msg_queues', 'rasa_reaponse_queues', 'rasaAgent'] -> ['rasa_msg_queues', 'rasa_response_queues', 'rasa_agent']
    - Return: None -> None
```

## 🐛 Troubleshooting

### Common errors

1. **File not found**
   ```
   ❌ The original file does not exist: original.py
   ```
   **Solution** : Check the file paths

2. **Syntax error**
   ```
   ❌ Syntax error in test.py: invalid syntax
   ```
   **Solution** : Fix syntax errors before validation

3. **Missing import**
   ```
   ❌ Import error: cannot import name 'module' from 'package'
   ```
   **Solution** : The tool continues despite missing imports

### Verbose mode

Use `--verbose` to see process details:
```bash
python module_interchangeability_validator.py original.py test.py --verbose
```

## 🔄 Continuous integration

### GitHub Actions
```yaml
- name: Validate module interchangeability
  run: |
    python module_interchangeability_validator.py original.py test.py --score-only
    if [ $? -ne 0 ]; then
      echo "Module incompatibility detected"
      exit 1
    fi
```

## 📝 Technical notes

### Current limitations

1. **External dependencies** : The tool cannot validate uninstalled dependencies
2. **Dynamic execution** : Does not execute the code, static analysis only
3. **Metaprogramming** : May not detect certain dynamic changes

### Future improvements

- Support for `.pyi` files (type hints)
- Analysis of docstrings
- Detection of side effects
- Support for multiple packages

## 📞 Support

For any questions or issues, please refer to:
1. The documentation above
2. Verbose mode (`--verbose`)
3. Usage examples

---

**Author** : GitHub Copilot  
**Version** : 1.0  
**Date** : October 7, 2025