'use strict';

// this is a very over-engineered solution that took a long time to make.
// derp.

$(document).ready(function()
{
    $('.button-collapse').sideNav();
});

angular.module('themes', [])
    .controller('themer', ['$scope', function($scope)
    {
        $scope.themedItems = $scope.themedItems || [];
        $scope.theme = $scope.theme || localStorage.theme || "Dark";

        // add and set the current theme
        this.addThemedItem = function(item)
        {
            $scope.themedItems.push(item);
        }
        this.setTheme = function(theme)
        {
            $scope.theme = theme;
            localStorage.theme = theme;

            angular.forEach($scope.themedItems, function(item)
            {
                item.e.attr('class', item.a['theme' + theme]);
            });
        }

        // apply initial theming
        $scope.$watch('themedItems', function()
        {
            angular.forEach($scope.themedItems, function(item)
            {
                item.e.attr('class', item.a['theme' + $scope.theme]);
            });
        });
    }])
    .directive('theme', function()
    {
        // this element is themed
        let link = function(scope, element, attrs, controller)
        {
            controller.addThemedItem({e: element, a: attrs});
        }

        return {
            link: link,
            controller: 'themer'
        }
    })
    .directive('themeSet', function()
    {
        // this element sets the theme
        let link = function(scope, element, attrs, controller)
        {
            element.on('click', function()
            {
                controller.setTheme(attrs.themeSet);
            });
        }

        return {
            link: link,
            controller: 'themer'
        };
    });