from setuptools import find_packages, setup

setup(
    name="liftosaur-garmin-uploader",
    version="1.3.1",
    description="Convert Liftosaur workouts to Garmin FIT and upload",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "garth",
        "pytest",
        "fitparse",
        "pyobjc; platform_system == 'Darwin'",
    ],
    entry_points={
        "console_scripts": [
            "liftosaur-garmin=liftosaur_garmin.cli:main",
        ]
    },
)
