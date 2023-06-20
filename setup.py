import pathlib

import setuptools

# The directory containing this file
TOPLEVEL_DIR = pathlib.Path(__file__).parent.absolute()
ABOUT_FILE = TOPLEVEL_DIR / "omc3_gui" / "__init__.py"
README = TOPLEVEL_DIR / "README.md"

# Information on the omc3_gui package
ABOUT_OMC3_GUI: dict = {}
with ABOUT_FILE.open("r") as f:
    exec(f.read(), ABOUT_OMC3_GUI)

with README.open("r") as docs:
    long_description = docs.read()

# Dependencies for the package itself
DEPENDENCIES = [
    f"omc3[optional]>={ABOUT_OMC3_GUI['__omc3_version__']}",
    "PyQt5>=5.15.7",  # Keep PyQT5 for now, until acc-py updates 
]

# Extra dependencies
EXTRA_DEPENDENCIES = {
    "cern": [
        f"omc3[cern]>={ABOUT_OMC3_GUI['__omc3_version__']}",
        # "accwidgets[app_frame,rbac,log_console,screenshot,graph]",
    ],
    "test": [
        "pytest>=5.2",
        "pytest-cov>=2.7",
        "pytest-timeout>=1.4",
    ],
    "doc": [
        "sphinx",
        "sphinx_rtd_theme",
    ],
}
EXTRA_DEPENDENCIES.update(
    {"all": [elem for list_ in EXTRA_DEPENDENCIES.values() for elem in list_]}
)


setuptools.setup(
    name=ABOUT_OMC3_GUI["__title__"],
    version=ABOUT_OMC3_GUI["__version__"],
    description=ABOUT_OMC3_GUI["__description__"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=ABOUT_OMC3_GUI["__author__"],
    author_email=ABOUT_OMC3_GUI["__author_email__"],
    url=ABOUT_OMC3_GUI["__url__"],
    packages=setuptools.find_packages(exclude=["tests*", "doc"]),
    include_package_data=True,
    python_requires=">=3.7",
    license=ABOUT_OMC3_GUI["__license__"],
    classifiers=[
        "Intended Audience :: Science/Research",
        f"License :: OSI Approved :: {ABOUT_OMC3_GUI['__license__']}",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Visualization",
    ],
    install_requires=DEPENDENCIES,
    tests_require=EXTRA_DEPENDENCIES["test"],
    extras_require=EXTRA_DEPENDENCIES,
)
