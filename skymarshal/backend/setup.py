from setuptools import setup, find_packages

setup(
    name="skymarshal",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "flask>=2.0.0",
        # other dependencies
    ],
    author="Your Name",
    description="Skymarshal CLI and backend APIs",
    long_description=open("../README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/skymarshal",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
