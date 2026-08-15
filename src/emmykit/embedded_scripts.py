"""embedded_scripts — extracted from univ_defs.py."""

from __future__ import annotations

# The five standalone command-line programs that used to live here
# (PRINTALL_SCRIPT, MYDIFF_SCRIPT, MYAUDIT_SCRIPT, MULTIREPLACE_SCRIPT,
# TREEVIEW_SCRIPT) moved to https://github.com/killett/utilities in 0.4.0,
# where they are real .py files that can be linted, typed and tested.
# UNIV_DEFS_SYS_PATH_SCRIPT was deleted rather than moved: emmykit is an
# installed package, so `import emmykit` already works without a sys.path shim.

SETUP_CARTOPY_SCRIPT: str = r'''import os
import matplotlib.pyplot as plt
import cartopy
cartopy.config["data_dir"] = os.getenv("CARTOPY_DATA_DIR", cartopy.config.get("data_dir"))

fig, ax = plt.subplots(subplot_kw={"projection": cartopy.crs.PlateCarree()})
# Explicitly specify resolution and add the ocean and land features to ensure pre-loading
ax.coastlines("110m")
ax.add_feature(cartopy.feature.OCEAN)
ax.add_feature(cartopy.feature.LAND)

# Force feature download
temp_filename = "cartopy_test_map.png"
plt.savefig(temp_filename)
os.remove(  temp_filename)
'''
