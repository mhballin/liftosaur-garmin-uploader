from setuptools import find_packages, setup

setup(
    name="liftosaur-garmin-uploader",
    version="0.1.0",
    description="Convert Liftosaur workouts to Garmin FIT and upload",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "liftosaur-garmin=liftosaur_garmin.cli:main",
        ]
    },
)
