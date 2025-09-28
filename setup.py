# setup.py
from setuptools import setup, find_packages

setup(
    name="bootupsoftware",
    version="1.0.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    package_data={"bootupsoftware": ["config.json"]},
    entry_points={"console_scripts": ["bootup=bootupsoftware.AppBootLaunch:main"]},
)
