from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).parent

setup(
    name="virtutrial-core",
    version="0.1.0",
    description=(
        "Synthetic control arms and digital-twin forecasts for clinical-trial research"
    ),
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="Subramani Nagaraj",
    url="https://github.com/snagaraj07/virtutrial-core",
    license="MIT",
    python_requires=">=3.9",
    package_dir={"": "src"},
    py_modules=[
        "simulator",
        "forecaster",
        "vca_engine",
        "schema",
        "privacy",
        "diagnostics",
        "runner",
        "workbench",
        "auth",
        "audit",
        "studies",
    ],
    install_requires=[
        "numpy>=1.24,<2",
        "pandas>=2.0",
        "pyarrow>=14",
        "scikit-learn>=1.3",
        "scipy>=1.11",
    ],
    extras_require={
        "dev": ["pytest>=7.0", "ruff>=0.6"],
        "workbench": [
            "fastapi>=0.115",
            "httpx>=0.27",
            "jinja2>=3.1",
            "python-multipart>=0.0.9",
            "uvicorn>=0.30",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
)
