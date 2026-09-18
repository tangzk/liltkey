from pathlib import Path
import tempfile
import unittest

from fcitx5_voice.theme import install_theme

ROOT = Path(__file__).resolve().parents[1]


class ThemeInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.data = self.home / 'data'
        self.config = self.home / 'config'
        self.classic = self.config / 'fcitx5/conf/classicui.conf'

    def existing(self, text):
        self.classic.parent.mkdir(parents=True, exist_ok=True)
        self.classic.write_text(text)

    def install(self):
        install_theme(ROOT, self.data, self.config)

    def test_first_install_enables_theme_and_copies_all_assets(self):
        self.install()
        text = self.classic.read_text()
        self.assertIn('Theme=liltkey-light', text)
        self.assertIn('Font="Noto Sans CJK SC Medium 13"', text)
        self.assertIn('UseAccentColor=False', text)
        self.assertIn('Vertical Candidate List=False', text)
        for source in (ROOT / 'themes/liltkey-light').iterdir():
            self.assertEqual((self.data / 'fcitx5/themes/liltkey-light' / source.name).read_bytes(),
                             source.read_bytes())

    def test_default_theme_migrates_preserving_custom_font_and_other_options(self):
        before = '# user settings\nTheme="default"\nFont="Sans 16"\nWheelForPaging=False\n'
        self.existing(before)
        self.install()
        text = self.classic.read_text()
        self.assertIn('Theme=liltkey-light', text)
        self.assertIn('Font="Sans 16"', text)
        self.assertIn('WheelForPaging=False', text)
        self.assertIn('# user settings', text)
        self.assertEqual((self.data / 'fcitx5-voice/theme-backup/classicui.conf').read_text(), before)

    def test_custom_theme_and_dark_preference_are_preserved_byte_for_byte(self):
        for before in ('Theme="my-theme"\nFont="Sans 15"\n',
                       'Theme=default-dark\n',
                       'Theme=default\nUseDarkTheme=True\nDarkTheme=my-dark\n'):
            with self.subTest(before=before):
                self.existing(before)
                self.install()
                self.assertEqual(self.classic.read_text(), before)
                (self.data / 'fcitx5-voice/theme-default.json').unlink()

    def test_upgrade_does_not_reset_later_theme_choice_or_recreate_removed_settings(self):
        self.install()
        self.existing('Theme=default\nFont="Sans 12"\n')
        self.install()
        self.assertEqual(self.classic.read_text(), 'Theme=default\nFont="Sans 12"\n')
        self.classic.unlink()
        self.install()
        self.assertFalse(self.classic.exists())

    def test_custom_theme_on_first_install_stays_untouched_on_upgrade(self):
        self.existing('Theme=custom\n')
        self.install()
        self.existing('Theme=default\n')
        self.install()
        self.assertEqual(self.classic.read_text(), 'Theme=default\n')

    def test_upgrade_refreshes_assets_without_changing_theme_preferences(self):
        self.install()
        installed = self.data / 'fcitx5/themes/liltkey-light/panel.png'
        installed.write_bytes(b'outdated asset')
        before = self.classic.read_bytes()
        self.install()
        self.assertEqual(installed.read_bytes(), (ROOT / 'themes/liltkey-light/panel.png').read_bytes())
        self.assertEqual(self.classic.read_bytes(), before)

    def test_existing_config_permissions_are_preserved(self):
        self.existing('Theme=default\n')
        self.classic.chmod(0o600)
        self.install()
        self.assertEqual(self.classic.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
