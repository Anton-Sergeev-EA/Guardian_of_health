"""
Setup script for the FocusGuardian C++ Video Engine extension.
Provides cross-platform compilation configurations for Windows, macOS, and Linux.
"""

import os
import sys
import subprocess
from setuptools import setup, Extension

# Ensure build-time dependencies are available.
try:
    import pybind11
    import numpy as np
except ImportError:
    print("Error: Missing build dependencies. Please install them first:")
    print("pip install pybind11 numpy")
    sys.exit(1)

# Default configuration parameters.
extra_compile_args = []
extra_link_args = []
libraries = ['opencv_core', 'opencv_videoio', 'opencv_imgproc']
library_dirs = []
include_dirs = [
    pybind11.get_include(),
    np.get_include()
]

def query_pkg_config(lib_name, option):
    """Safely query pkg-config for compiler/linker flags on Unix-like systems."""
    try:
        cmd = ['pkg-config', option, lib_name]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8')
        return [flag.strip() for flag in output.split() if flag.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

# Platform-Specific Configurations.

if sys.platform == 'win32':
    # Windows (MSVC) Configuration.
    # Note: Adjust the OpenCV path if your local installation differs.
    OPENCV_DIR = os.environ.get('OPENCV_DIR', 'C:/opencv/build')
    
    extra_compile_args = [
        '/std:c++17',
        '/O2',       # Maximum optimization for speed.
        '/MT',       # Link with multithreaded static run-time library.
        '/GL',       # Whole program optimization.
        '/arch:AVX2' # Enable AVX2 vectorization (modern CPUs).
    ]
    extra_link_args = ['/LTCG'] # Link-time code generation.
    
    # Specific OpenCV world monolithic binary for Windows.
    libraries = ['opencv_world490'] 
    library_dirs = [os.path.join(OPENCV_DIR, 'x64/vc15/lib')]
    include_dirs.append(os.path.join(OPENCV_DIR, 'include'))

elif sys.platform == 'darwin':
    # macOS Configuration (Clang).
    extra_compile_args = [
        '-std=c++17',
        '-O3',
        '-march=native',
        '-flto',
        '-ffast-math',
        '-fomit-frame-pointer'
    ]
    extra_link_args = ['-flto']
    
    # Attempt to dynamically locate OpenCV via pkg-config (Homebrew default).
    pkg_includes = query_pkg_config('opencv4', '--cflags-only-I')
    pkg_libs = query_pkg_config('opencv4', '--libs-only-L')
    
    if pkg_includes:
        include_dirs.extend([path[2:] for path in pkg_includes]) # Strip '-I' prefix.
    else:
        include_dirs.append('/opt/homebrew/include/opencv4') # Apple Silicon fallback.
        include_dirs.append('/usr/local/include/opencv4')     # Intel fallback
        
    if pkg_libs:
        library_dirs.extend([path[2:] for path in pkg_libs]) # Strip '-L' prefix.
    else:
        library_dirs.append('/opt/homebrew/lib')
        library_dirs.append('/usr/local/lib')

else:
    # Linux Configuration (GCC/Clang).
    extra_compile_args = [
        '-std=c++17',
        '-O3',
        '-march=native',
        '-flto=auto',
        '-ffast-math',
        '-fomit-frame-pointer',
        '-fPIC'
    ]
    extra_link_args = ['-flto=auto']
    
    # Attempt to dynamically locate OpenCV via pkg-config.
    pkg_includes = query_pkg_config('opencv4', '--cflags-only-I')
    pkg_libs = query_pkg_config('opencv4', '--libs-only-L')
    
    if pkg_includes:
        include_dirs.extend([path[2:] for path in pkg_includes])
    else:
        include_dirs.append('/usr/include/opencv4')
        
    if pkg_libs:
        library_dirs.extend([path[2:] for path in pkg_libs])
    else:
        library_dirs.append('/usr/lib/x86_64-linux-gnu')

# Module Definition.

video_module = Extension(
    name='src.core.video_engine',
    sources=['src/core/video_engine.cpp'],
    include_dirs=include_dirs,
    libraries=libraries,
    library_dirs=library_dirs,
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args,
    language='c++'
)

# Packaging Setup.
setup(
    name='focus-guardian',
    version='2.0.0',
    description='AI Health Assistant with a high-performance C++ video engine',
    author='FocusGuardian Team',
    ext_modules=[video_module],
    packages=['src', 'src.core', 'src.analytics', 'src.voice', 'src.ui', 'src.web'],
    zip_safe=False,
    python_requires='>=3.12',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Programming Language :: C++',
        'Programming Language :: Python :: 3.12',
        'Topic :: Multimedia :: Video :: Capture',
    ]
)
