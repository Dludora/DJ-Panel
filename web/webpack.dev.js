const { merge } = require('webpack-merge')
const webpack = require('webpack')
const webpackShared = require('./webpack.common.js')
const CopyPlugin = require('copy-webpack-plugin')
const path = require('path')

// look for elkjs package folder
const elkjsRoot = path.dirname(require.resolve('elkjs/package.json'));
const apiTarget =
  process.env.DJ_PANEL_API_ORIGIN ||
  `http://${process.env.MARQUEZ_HOST || 'localhost'}:${process.env.MARQUEZ_PORT || 5000}/`

const webpackDev = {
  mode: 'development',
  devServer: {
    static: {
      directory: __dirname + '/src',
      staticOptions: {},
      publicPath: "/",
      serveIndex: true,
      watch: true,
    },
    host: process.env.DJ_PANEL_WEB_HOST || '127.0.0.1',
    port: Number(process.env.DJ_PANEL_WEB_PORT || 1337),
    open: process.env.DJ_PANEL_WEB_OPEN === '1',
    devMiddleware: {
      publicPath: '/'
    },
    historyApiFallback: {
      index: './index.html',
      disableDotRule: true
    },
    proxy: {
      '/api': {
        target: apiTarget,
        secure: false,
        logLevel: 'debug',
        headers: {
          'X-Bifrost-Authentication': 'developer'
        }
      }
    }
  },
  // Enable sourcemaps for debugging webpack"s output.
  devtool: 'eval-cheap-module-source-map',
  plugins: [
    new webpack.DefinePlugin({
      __DEVELOPMENT__: JSON.stringify(true),
      __REACT_APP_ADVANCED_SEARCH__: true,
      __API_URL__: JSON.stringify('/api/v1'),
      __API_BETA_URL__: JSON.stringify('/api/v2beta'),
      __NODE_ENV__: JSON.stringify('development'),
      __TEMP_ACTOR_STR__: JSON.stringify('me'),
      __FEEDBACK_FORM_URL__: JSON.stringify('https://forms.gle/f3tTSrZ8wPj3sHTA7'),
      __API_DOCS_URL__: JSON.stringify('https://marquezproject.github.io/marquez/openapi.html')
    }),
      new CopyPlugin({
        patterns: [
          { from: path.join(elkjsRoot, 'lib/elk-worker.min.js'), to: 'elk-worker.min.js' },
        ],
      }),
  ]
}

module.exports = merge(webpackShared, webpackDev)
