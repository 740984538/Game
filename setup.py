from setuptools import setup, find_packages

setup(
    name="roguelike-game",
    version="0.1.0",
    description="深渊回响：无尽轮回 - 单机Roguelike游戏",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "pygame>=2.5.0",
        # 项目使用 esper 2.x 的 World/Processor API，不兼容 esper 3.x
        "esper>=2.5,<3.0",
        "PyYAML>=6.0",
        "numpy>=1.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "mypy>=1.0",
            "black>=23.0",
        ],
        "optional": [
            "loguru>=0.7.0",
            "Cython>=3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "roguelike=main:main",
        ],
    },
)
