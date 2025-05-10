# Contributing to WireGuard VPN Tunnel Manager

Thank you for considering contributing to the WireGuard VPN Tunnel Manager! This document outlines the process for contributing to the project.

## Code of Conduct

This project is maintained by WEE Technology Solutions Ltd. and we expect all contributors to adhere to the following code of conduct:

1. Be respectful of other contributors
2. Communicate openly and considerately
3. Focus on what is best for the community
4. Show courtesy and respect towards other community members

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue in the GitHub repository with the following information:

1. A clear, descriptive title
2. A detailed description of the issue
3. Steps to reproduce the bug
4. Expected behavior
5. Actual behavior
6. Screenshots if applicable
7. Your environment (OS, Python version, etc.)

### Suggesting Enhancements

We welcome suggestions for enhancements! Please open an issue with:

1. A clear, descriptive title
2. A detailed description of the proposed enhancement
3. Any specific implementation details you have in mind
4. Why this enhancement would be useful to most users

### Pull Requests

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Implement your changes
4. Ensure your code follows the project's style guidelines
5. Include appropriate tests
6. Update documentation as necessary
7. Submit a pull request

## Development Setup

To set up the project for development:

1. Clone the repository
2. Install the dependencies in a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

3. Run tests:
   ```bash
   pytest
   ```

## Coding Style

We follow PEP 8 for Python code. Some key points:

- Use 4 spaces for indentation
- Use snake_case for variables and function names
- Use CamelCase for class names
- Keep lines under 100 characters
- Write docstrings for all functions, classes, and modules

## License

By contributing to this project, you agree that your contributions will be licensed under the project's MIT License.

## Contact

If you have any questions, feel free to contact:

- Shalinda Jayasinghe - WEE Technology Solutions Ltd.
- GitHub Issues: [Project Issues Page](https://github.com/wee-technology-solutions/wireguard-vpn-tunnel-manager/issues)

Thank you for your contributions!