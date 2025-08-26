# ANAT 

ANAT is a Python-based tool that can be installed and run on Termux. This guide will help you quickly set up ANAT on your device.

---

## 📥 F-Droid Installation (Optional)

You can install F-Droid to manage apps if needed:

**Download Link:** [F-Droid APK](https://f-droid.org/F-Droid.apk)

1. Download and install the APK.
2. After the app updates, click the search option and type: `Termux API`.
3. Install Termux API if prompted.  
   - If it shows "Open," you can open it; otherwise, installation is complete.

---

## 🛠 Termux Installation

Follow these steps to install and run ANAT on Termux:

```bash
# Update and upgrade packages
apt update && apt upgrade

# install termux-api
pkg install-api

# Install Python
pkg install python

# Install Git
pkg install git

# Clone the ANAT repository
git clone https://github.com/fkunknownteam/ANAT
cd ANAT

# Install required Python packages
pip install -r requenst.txt

# Run ANAT
python ANAT.py
