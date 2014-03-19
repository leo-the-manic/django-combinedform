import setuptools


def read_file(filename):
    with open(filename) as infile:
        return infile.read()


setuptools.setup(
    description="Compose Django forms",
    install_requires=['django'],
    license="LGPL3",
    long_description=read_file("README.rst"),
    maintainer_email="manicleo@gmail.com",
    maintainer_name="leo-the-manic",
    name="django-combinedforms",
    packages=['combinedform'],
    url="https://github.com/leo-the-manic/django-combinedform",
    version="0.1.5",
)
