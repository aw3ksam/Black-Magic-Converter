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
    osxSign: {
      entitlements: './entitlements/entitlements.mac.plist',
      'entitlements-inherit': './entitlements/entitlements.mac.inherit.plist',
      'hardened-runtime': true,
      'gatekeeper-assess': false,
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
    {
      name: '@electron-forge/maker-deb',
      config: {
        options: {
          icon: './assets/icons/icon.png',
          categories: ['AudioVideo', 'Video'],
          description: 'Automated Blackmagic RAW Transcoder & Workstation',
        },
      },
    },
    {
      name: '@electron-forge/maker-rpm',
      config: {
        options: {
          icon: './assets/icons/icon.png',
          categories: ['AudioVideo', 'Video'],
          description: 'Automated Blackmagic RAW Transcoder & Workstation',
        },
      },
    },
  ],
  plugins: [
    {
      name: '@electron-forge/plugin-vite',
      config: {
        // `build` can specify multiple entry builds, which can be Main process, Preload scripts,
        // Worker process, etc.
        build: [
          {
            // `entry` is an alias for `build.lib.entry` in the corresponding Vite config
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
    // Fuses are used to enable/disable various Electron functionality
    // at package time, before code signing the application
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],
};
