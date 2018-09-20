from setuptools import setup, find_packages


setup(
    name='aiowx',
    version='0.5',
    description='Asyncio-based client for Wei Xin Platform',
    author='Rocky Feng',
    author_email='folowing@gmail.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['aiohttp>=3.0.0'],
    zip_safe=False,
)
