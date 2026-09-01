const { FusesPlugin } = require('@electron-forge/plugin-fuses');
const { FuseV1Options, FuseVersion } = require('@electron/fuses');

module.exports = {
  packagerConfig: {
    name: 'Black Magic Converter',
    executableName: 'BlackMagicConverter',
    appBundleId: 'com.blackmagic.converter',
    appCategoryType: 'public.app-category.video',
    icon: './assets/icons/icon',
    asar: true,
    osxSign: process.env.APPLE_ID || process.env.APPLE_SIGN_IDENTITY
      ? {
          identity: process.env.APPLE_SIGN_IDENTITY,
          entitlements: './entitlements/entitlements.mac.plist',
          'entitlements-inherit': './entitlements/entitlements.mac.inherit.plist',
          'hardened-runtime': true,
          'gatekeeper-assess': false,
        }
      : {
          identity: '-',
          entitlements: './entitlements/entitlements.mac.plist',
          'entitlements-inherit': './entitlements/entitlements.mac.inherit.plist',
          'hardened-runtime': false,
        },
    osxNotarize: process.env.APPLE_ID
      ? {
          appleId: process.env.APPLE_ID,
          appleIdPassword: process.env.APPLE_PASSWORD,
          teamId: process.env.APPLE_TEAM_ID,
        }
      : undefined,
  },
  rebuildConfig: {},
  makers: [
    {
      name: '@electron-forge/maker-squirrel',
      config: {
        name: 'BlackMagicConverter',
        authors: 'Antigravity Studio',
        description: 'Automated Blackmagic RAW Transcoder & Workstation',
        iconUrl: 'https://raw.githubusercontent.com/blackmagic/converter/main/assets/icons/icon.ico',
        setupIcon: './assets/icons/icon.ico',
      },
    },
    {
      name: '@electron-forge/maker-zip',
      platforms: ['darwin', 'win32', 'linux'],
    },
    {
      name: '@electron-forge/maker-dmg',
      config: {
        name: 'BlackMagicConverter',
        icon: './assets/icons/icon.icns',
        format: 'ULFO',
      },
    },
  ],
  plugins: [
    {
      name: '@electron-forge/plugin-vite',
      config: {
        build: [
          {
            entry: 'src/electron/main/index.js',
            config: 'vite.main.config.mjs',
            target: 'main',
          },
          {
            entry: 'src/electron/preload/index.js',
            config: 'vite.preload.config.mjs',
            target: 'preload',
          },
        ],
        renderer: [
          {
            name: 'main_window',
            config: 'vite.renderer.config.mjs',
          },
        ],
      },
    },
  ],
};
