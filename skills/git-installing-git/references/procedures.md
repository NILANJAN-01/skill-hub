# More procedures: Installing Git

### Installing from Source

**Goal:** Some people may instead find it useful to install Git from source, because you’ll get the most recent version.

**Steps:**

1. For example, if you’re on a system that has `dnf` (such as Fedora) or `apt-get` (such as a Debian-based system), you can use one of these commands to install the minimal dependencies for compiling and installing the Git binaries:
   ```bash
   sudo dnf install dh-autoreconf curl-devel expat-devel gettext-devel \
   openssl-devel perl-devel zlib-devel
   sudo apt-get install dh-autoreconf libcurl4-gnutls-dev libexpat1-dev \
   gettext libz-dev libssl-dev
   ```
2. In order to be able to add the documentation in various formats (doc, html, info), these additional dependencies are required:
   ```bash
   sudo dnf install asciidoc xmlto docbook2X
   sudo apt-get install asciidoc xmlto docbook2x
   ```
3. If you’re using a Debian-based distribution (Debian/Ubuntu/Ubuntu-derivatives), you also need the `install-info` package:
   ```bash
   sudo apt-get install install-info
   ```
4. If you’re using a RPM-based distribution (Fedora/RHEL/RHEL-derivatives), you also need the `getopt` package (which is already installed on a Debian-based distro):
   ```bash
   sudo dnf install getopt
   ```
5. Additionally, if you’re using Fedora/RHEL/RHEL-derivatives, you need to do this:
   ```bash
   sudo ln -s /usr/bin/db2x_docbook2texi /usr/bin/docbook2x-texi
   ```
6. Then, compile and install:
   ```bash
   tar -zxf git-2.8.0.tar.gz
   cd git-2.8.0
   make configure
   ./configure --prefix=/usr
   make all doc info
   sudo make install install-doc install-html install-info
   ```
7. After this is done, you can also get Git via Git itself for updates:
   ```bash
   git clone https://git.kernel.org/pub/scm/git/git.git
   ```
