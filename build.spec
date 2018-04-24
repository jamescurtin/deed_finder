import gooey

gooey_root = os.path.dirname(gooey.__file__)
gooey_languages = Tree(os.path.join(gooey_root, 'languages'), prefix = 'gooey/languages')
gooey_images = Tree(os.path.join(gooey_root, 'images'), prefix = 'gooey/images')

a = Analysis(['deed_finder.py'],
             pathex=['/usr/local/bin/python3'],
             hiddenimports=[],
             hookspath=None,
             datas=[('chromedriver', '.'),
             ('images', 'images')],
             runtime_hooks=None,
             )

pyz = PYZ(a.pure)

options = [('u', None, 'OPTION')]

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          options,
          gooey_languages,
          gooey_images,
          name='deed_finder',
          strip=None,
          upx=False,
          console=False,
          icon='images/config_icon.icns')

app = BUNDLE(exe,
         name='Deed Finder.app',
         icon='images/config_icon.icns',
         bundle_identifier=None,
         info_plist={
            'CFBundleName': 'Deed Finder',
            'CFBundleDisplayName': 'Deed Finder',
            'CFBundleGetInfoString': "Deed Finder",
            'CFBundleVersion': "0.1.0",
            'CFBundleShortVersionString': "0.1.0",
            'NSHumanReadableCopyright': u"Copyright © 2018, James Curtin",
            'NSHighResolutionCapable': 'True'
    })

