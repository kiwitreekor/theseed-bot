from setuptools import find_packages, setup

setup(
    name='theseed-bot',
    version='2.5.6',
	description='theseed engine api',
	url='https://github.com/kiwitreekor/theseed-bot',
	author='kiwitree',
	author_email='kiwitreekor@gmail.com',
	packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent"
    ],
    python_requires='>=3.7'
)