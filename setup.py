from setuptools import setup, find_packages
import os
import re

# Read version from src/__init__.py
with open(os.path.join('src', '__init__.py'), 'r') as f:
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        raise RuntimeError("Unable to find version string in src/__init__.py")

# Read long description from README.md
with open('README.md', 'r') as f:
    long_description = f.read()

# Read requirements from requirements.txt
with open('requirements.txt', 'r') as f:
    requirements = f.read().splitlines()

setup(
    name="transferbox",
    version=version,
    author="Tyler",
    author_email="your.email@example.com",  # Replace with your email
    description="A utility for secure file transfers with verification",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/transferbox",  # Replace with your repository URL
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "transferbox=main:main",
        ],
    },
    include_package_data=True,
) 