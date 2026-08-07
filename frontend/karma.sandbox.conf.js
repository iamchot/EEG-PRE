module.exports = function (config) {
  config.set({
    basePath: '',
    frameworks: ['jasmine', '@angular-devkit/build-angular'],
    plugins: [
      require('karma-jasmine'),
      require('karma-chrome-launcher'),
      require('karma-jasmine-html-reporter'),
      require('karma-coverage'),
      require('@angular-devkit/build-angular/plugins/karma'),
    ],
    customLaunchers: {
      ChromeHeadlessSandbox: {
        base: 'ChromeHeadless',
        flags: ['--disable-gpu', '--disable-software-rasterizer', '--disable-dev-shm-usage', '--no-sandbox'],
      },
    },
    reporters: ['progress', 'kjhtml'],
    browsers: ['ChromeHeadlessSandbox'],
    restartOnFileChange: false,
  });
};
