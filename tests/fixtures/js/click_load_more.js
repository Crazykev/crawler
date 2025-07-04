// JavaScript test file for clicking "Load More" button
// Used in CLI tests for --js-code option

(function() {
    // Find and click "Load More" button
    const loadMoreButton = document.querySelector('button[onclick*="loadMore"], .load-more, #load-more');
    if (loadMoreButton) {
        loadMoreButton.click();
        console.log('Clicked load more button');
        
        // Wait for content to load
        return new Promise((resolve) => {
            setTimeout(() => {
                console.log('Load more action completed');
                resolve();
            }, 1000);
        });
    } else {
        console.log('Load more button not found');
    }
})();