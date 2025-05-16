from setuptools import setup, find_packages

setup(
    name="weather_app",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "RPi.GPIO",
        "spidev",
        "Pillow",
    ],
    python_requires=">=3.6",
)