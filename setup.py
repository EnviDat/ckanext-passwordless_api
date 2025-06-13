from setuptools import setup, find_packages

version = "1.1.8"

setup(
    name="ckanext-passwordless_api",
    version=version,
    description="Extension to allow paswordless login to the CKAN API.",
    classifiers=[
        "Topic :: Utilities",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10"
    ],
    keywords = ["CKAN", "passwordless", "token", "auth"],
    author="Sam Woodcock",
    url="https://gitlabext.wsl.ch/EnviDat/ckanext-passwordless_api/-/tree/ckan-2-11",
    license="MIT",
    packages=find_packages(),
    namespace_packages=["ckanext"],
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    entry_points="""
    [ckan.plugins]
    passwordless_api=ckanext.passwordless_api.plugin:PasswordlessAPIPlugin
    """,
)
