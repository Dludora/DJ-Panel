const postCssModulesValues = require("postcss-modules-values")
const path = require('path')
const autoprefixer = require('autoprefixer')

module.exports = {
  entry: './src/index.tsx',
  ignoreWarnings: [
    {
      module: /framer-motion[\\/]dist[\\/]cjs[\\/]feature-bundle.*\.js$/,
      message: /Critical dependency: the request of a dependency is an expression/,
    },
  ],
  module: {
    rules: [{
        test: /\.css$/,
      use: [{
            loader: 'style-loader',
          },
          {
            loader: 'css-loader',
            options: {
              importLoaders: 1,
              modules : {
                localIdentName: '[name]__[local]__[hash:base64:5]',
              },
            }
        }]
      },
      {
        test: /\.(png|jpe?g|gif|svg)(\?v=\d+\.\d+\.\d+)?$/,
        loader: 'file-loader'
      },
      {
        test: /\.(woff(2)?|ttf|eot|otf)(\?v=\d+\.\d+\.\d+)?$/,
        use: [{
          loader: 'file-loader',
          options: {
            name: '[name].[ext]',
            outputPath: 'fonts/'
          }
        }]
      },
      // All files with a '.ts' or '.tsx' extension will be handled by 'ts-loader'.
      {
        test: /\.tsx?$/,
        loader: "ts-loader"
      },
      {
        test: /\.ico$/,
        loader: 'file-loader'
      }
    ]
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js', '.json'],
    symlinks: false,
    alias: {
      'd3-interpolate': path.resolve(__dirname, 'node_modules/d3-interpolate'),
      'd3-selection': path.resolve(__dirname, 'node_modules/d3-selection'),
      'd3-transition': path.resolve(__dirname, 'node_modules/d3-transition'),
      'd3-zoom': path.resolve(__dirname, 'node_modules/d3-zoom'),
      react: path.resolve(__dirname, 'node_modules/react'),
      'react/jsx-runtime': path.resolve(__dirname, 'node_modules/react/jsx-runtime.js'),
      'react/jsx-dev-runtime': path.resolve(__dirname, 'node_modules/react/jsx-dev-runtime.js'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
      'react-router-dom': path.resolve(__dirname, 'node_modules/react-router-dom'),
    },
  },
  output: {
    filename: 'bundle.js',
    path: path.resolve(__dirname, 'dist'),
    publicPath: '/'
  }
};
