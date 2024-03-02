from pathlib import Path

from setuptools import find_packages
from setuptools import setup

requirements = []
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="tansy",
    description="Unstable experiments with interactions.py.",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    author="AstreaTSS",
    url="https://github.com/Astrea-Stellarium-Labs/tansy",
    version="0.9.1",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
