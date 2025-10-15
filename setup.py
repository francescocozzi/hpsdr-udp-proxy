"""
Setup script for HPSDR UDP Proxy
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
if requirements_file.exists():
    requirements = requirements_file.read_text().strip().split('\n')
    requirements = [r.strip() for r in requirements if r.strip() and not r.startswith('#')]
else:
    requirements = []

setup(
    name="hpsdr-udp-proxy",
    version="0.1.0",
    author="HPSDR Proxy Team",
    author_email="",
    description="High-performance UDP proxy for HPSDR protocol with authentication",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Communications :: Ham Radio",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'hpsdr-proxy=main:main',
        ],
    },
    include_package_data=True,
    package_data={
        'hpsdr_proxy': [
            'config/*.yaml',
            'database/*.sql',
        ],
    },
)
