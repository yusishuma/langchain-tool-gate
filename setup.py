from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="langchain-tool-gate",
    version="1.0.0",
    description="Tool governance and auditing framework for LangChain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="yusishuma",
    author_email="yusilovechina@icloud.com",
    license="MIT",
    packages=["tool_governance", "tool_governance.core", "tool_governance.cli", "tool_governance.integrations"],
    package_dir={"": "src"},
    install_requires=[
        "langchain>=0.3.0",
        "sqlalchemy",
        "click",
        "tabulate",
        "pydantic>=2.0.0",
        "python-dotenv",
        "prometheus-client",
    ],
    extras_require={
        "dev": [
            "pytest",
            "build",
            "twine",
        ],
    },
    entry_points={
        "console_scripts": [
            "tool-gov=tool_governance.cli.main:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
    ],
    python_requires=">=3.9",
)