# AGENTS.md - Development Guide for unuCharger Project

## Project Overview
This is a Python-based charger control system that manages smart home charging devices through Fritz!Box API integration. The project includes Flask web interfaces, automated charging algorithms, and comprehensive testing.

## Build/Test Commands

### Installation
```bash
# Install required dependencies
pip install numpy scipy fritzconnection flask time_machine mock

# Optional: install development tools
pip install flake8 black isort mypy pytest pytest-cov
```

### Running Tests
```bash
# Run all tests
python -m unittest discover test/

# Run single test file
PYTHONPATH=. python test/test_AutoCharger.py
PYTHONPATH=. python test/test_Charger.py  
PYTHONPATH=. python test/test_UnuCharger.py

# Run specific test method
PYTHONPATH=. python -m unittest test.test_UnuCharger.TestUnuCharger.test_UC

# Run with verbose output
python -m unittest discover test/ -v
```

### Running the Application
```bash
# Main charger control loop
python unuCharger.py [settings_file.json]

# Flask web interface
python app.py
python flaskHello.py

# Web interface for charger management
python UnuChargerWeb.py
```

### Code Quality
No formal linting/formatting configured. Consider adding:
- `pip install flake8 black isort mypy` for code quality
- `pip install pytest pytest-cov` for enhanced testing

## Code Style Guidelines

### Import Organization
- Standard library imports first (os, sys, time, json)
- Third-party imports second (numpy, scipy, flask, fritzconnection)  
- Local imports last (unuCharger modules)
- Type imports from `typing` module grouped together
- Use `from module import Class` for frequently used classes
- Use `import module` for modules referenced with dot notation

```python
import os.path
import sys
import time
from datetime import datetime

import numpy as np
import statistics
from fritzconnection import FritzConnection
from scipy.stats import linregress
from typing import Any, List, Dict

import unuCharger
```

### Naming Conventions
- **Classes**: PascalCase (e.g., `Charger`, `AutoCharger`, `ThresholdCharger`)
- **Functions/Methods**: camelCase for public methods, snake_case for private/internal
- **Variables**: camelCase (e.g., `statsPoolSize`, `triggerPowerMW`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `CHARGING`, `NOT_CHARGING`, `CHARGED`)
- **File names**: snake_case or PascalCase for main modules (`unuCharger.py`, `app.py`)

### Type Hints
- Use type hints for all function signatures and class attributes
- Import specific types from `typing` module
- Use `Any` for external dependencies like `FritzConnection`
- Use Union types with `|` syntax (Python 3.10+) for return types

```python
def evaluate(self) -> int:
def detectCharger(self) -> Charger | None:
def createCharger(fc:FritzConnection, frequencyS:int, json:Dict[str,Any])->Charger:
```

### Error Handling
- Use try/catch blocks for external API calls
- Print exceptions to stderr with context
- Return default values (0, None) when operations fail
- Use specific exception types where possible
- Implement graceful degradation for network issues

```python
try:
    jsn = self.fritzCon.call_http(command, self.AIN)
    reti = int(jsn['content'])
except Exception as error:
    print("An exception occurred:", error)
    reti = 0
return reti
```

### Documentation
- Use docstrings for classes and complex methods
- Explain algorithm logic in comments
- Document constants and configuration values
- Use inline comments for non-obvious calculations
- Include parameter and return value documentation

### File Organization
- Main application logic in `unuCharger.py` 
- Web interfaces in `app.py`, `flaskHello.py`, `UnuChargerWeb.py`
- Tests in `test/` directory with `test_*.py` naming
- Configuration in `settings.json` (ignored in git)
- Log files generated as `{name}.tab` and `{name}.debug.txt`

### Constants and Magic Numbers
- Define power thresholds as class constants
- Use descriptive variable names for calculations
- Comment on power values (MW vs W) and conversion factors
- Centralize configuration in JSON settings file

### Testing Patterns
- Use `unittest.TestCase` for all test classes
- Mock external dependencies with `unittest.mock`
- Use `MagicMock` with `side_effect` for sequence returns
- Test time-dependent behavior with `time_machine` library
- Include setup methods for test configuration
- Use descriptive test method names
- Test both happy path and error conditions

### Configuration Management
- Store settings in JSON format
- Support command-line override of settings file path
- Use sensible defaults for optional parameters
- Handle missing configuration gracefully
- Separate per-device and global settings

### Logging and Debugging
- Use print statements for logging (consider upgrading to logging module)
- Separate log and debug file streams
- Include timestamps and relative timing information
- Use tab-separated format for data logs
- Truncate large log files to prevent disk usage issues

### Performance Considerations
- Use circular buffers for power readings (fixed size lists)
- Filter out noise values before calculations
- Use median for robust statistics
- Implement power-efficient sleep intervals
- Cache external API responses where appropriate

### Integration Notes
- Requires `fritzconnection` library for Fritz!Box API
- Uses `numpy` and `scipy` for statistical calculations
- Flask for web interface components
- `time_machine` for time-based test mocking
- All dependencies should be listed in requirements.txt (not present)