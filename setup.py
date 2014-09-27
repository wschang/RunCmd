from distutils.core import setup
from runcmd import __version__ as runcmd_version

setup(
    name='runcmd',
    version=runcmd_version,
    packages=[''],
    url='https://github.com/wschang/RunCmd',
    license='MIT',
    author='Wen Shan Chang',
    author_email='shan.and.android@gmail.com',
    description='Run commands with a timeout option'
)
