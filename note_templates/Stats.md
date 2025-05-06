
```dataviewjs
const totalApplications = dv.pages('"Hunt/Post"')
  .where(p => p.file.tags.includes("#jobpost") && p.applied === true)
  .length;

dv.paragraph(`## Total Counter: ${totalApplications}`);
```


## Daily
```dataviewjs
// Collect pages with 'date_applied' and convert them into an array of dates
var pagesArray = Array.from(dv.pages()
    .where(p => p.date_applied)
    .map(p => dv.date(p.date_applied).toFormat("yyyy-MM-dd")));

// Find the earliest and latest date in your dataset
var sortedPagesArray = [...pagesArray].sort();
var startDate = dv.date(sortedPagesArray[0]);
var endDate = dv.date(sortedPagesArray[sortedPagesArray.length - 1]);

// Generate all workdays (Monday to Friday) in the range
var allWorkdays = [];
for (var d = startDate; d <= endDate; d = d.plus({ days: 1 })) {
    if (d.weekday >= 1 && d.weekday <= 5) { // 1 is Monday, 5 is Friday
        allWorkdays.push(d.toFormat("yyyy-MM-dd"));
    }
}

// Count occurrences of each date
var dateCounts = allWorkdays.reduce((acc, date) => {
    acc[date] = (acc[date] || 0); // Initialize all dates with 0
    return acc;
}, {});

// Add counts from your data
pagesArray.forEach(date => {
    dateCounts[date] = (dateCounts[date] || 0) + 1;
});

// Convert the dateCounts object into an array of [date, count] pairs
var dateCountPairs = Object.entries(dateCounts);

// Sort the array by date
dateCountPairs.sort((a, b) => dv.date(a[0]) - dv.date(b[0]));

// Prepare labels and data for the chart
const labels = dateCountPairs.map(pair => pair[0]);
const jobApplications = dateCountPairs.map(pair => pair[1]);

// Chart configuration
const chartData = {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [{
            label: '#jobrec',
            data: jobApplications,
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
        }]
    },
    options: {
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
};

// Render the chart
window.renderChart(chartData, this.container);
```

## Weekly
```dataviewjs
// Collect pages with 'date_applied' and convert them into an array of dates
var pagesArray = Array.from(dv.pages()
    .where(p => p.date_applied)
    .map(p => dv.date(p.date_applied).toFormat("yyyy-MM-dd")));

// Ensure the pagesArray is sorted to correctly identify startDate and endDate
var sortedPagesArray = pagesArray.sort();
var startDate = dv.date(sortedPagesArray[0]); // Make sure this line exists and is correctly placed
var endDate = dv.date(sortedPagesArray[sortedPagesArray.length - 1]); // And this line too

// Function to get the year and week number for a date
function getYearWeek(d) {
    let date = new Date(d);
    date.setHours(0, 0, 0, 0);
    // Thursday in current week decides the year.
    date.setDate(date.getDate() + 3 - (date.getDay() + 6) % 7);
    // January 4 is always in week 1.
    let year = new Date(date.getFullYear(), 0, 4);
    // Adjust to Thursday in week 1 and count number of weeks from date to week1.
    let weekNum = 1 + Math.round(((date - year) / 86400000 - 3 + (year.getDay() + 6) % 7) / 7);
    return `${date.getFullYear()}-${weekNum < 10 ? '0' + weekNum : weekNum}`;
}

// Generate all weeks between startDate and endDate
var allWeeks = {};
for (var d = startDate; d <= endDate; d = d.plus({ days: 1 })) {
    let yearWeek = getYearWeek(d.toISODate());
    if (!allWeeks[yearWeek]) {
        allWeeks[yearWeek] = 0; // Initialize all year-weeks with 0
    }
}

// Add counts from your data to weeks
pagesArray.forEach(date => {
    let yearWeek = getYearWeek(date);
    allWeeks[yearWeek] = (allWeeks[yearWeek] || 0) + 1;
});

// Convert the allWeeks object into an array of [year-week, count] pairs and sort by year-week
var weekCountPairs = Object.entries(allWeeks).sort((a, b) => a[0].localeCompare(b[0]));

// Prepare labels and data for the chart
const labels = weekCountPairs.map(pair => `Week ${pair[0]}`);
const jobApplications = weekCountPairs.map(pair => pair[1]);

// Chart configuration
const chartData = {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [{
            label: '#jobrec',
            data: jobApplications,
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
        }]
    },
    options: {
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
};

// Render the chart
window.renderChart(chartData, this.container);
```

## Companies:
```dataviewjs
console.log("--- Dynamic Data Chart with Styling ---");

// 1. Query pages
const appliedPages = dv.pages('"Hunt/Post"')
  .where(p => p.file.tags.includes("#jobpost") && p.applied === true && p.company);

// 2. Group applications by company
const companyGroups = appliedPages.groupBy(p => p.company);

// 3. Prepare data (with strict checks and conversion)
let tempLabels = companyGroups
    .map(group => group.key === null || group.key === undefined ? null : String(group.key))
    .filter(label => label !== null && label.trim() !== '');

let tempCounts = companyGroups
    .map(group => Number(group.rows.length))
    .filter(count => !isNaN(count) && count >= 0);

// 4. Explicitly convert to standard JavaScript arrays
const labels = Array.from(tempLabels);
const applicationCounts = Array.from(tempCounts);

// --- Log final arrays ---
console.log("Final Labels:", labels);
console.log("Final Counts:", applicationCounts);
// --- End Logging ---

// 5. Check array lengths match after filtering
if (labels.length !== applicationCounts.length) {
    console.error("FATAL: Labels and Counts arrays have different lengths.", labels.length, applicationCounts.length);
    dv.paragraph("⚠️ Error: Mismatch between processed labels and counts. Check console.");
} else if (labels.length > 0) {
    // 6. Chart Configuration with Styling and Options RESTORED
    const chartData = {
        type: 'bar',
        data: {
            labels: labels, // Use STANDARD JS array
            datasets: [{
                label: 'Applications per Company',
                data: applicationCounts, // Use STANDARD JS array
                // --- Restore Styling ---
                backgroundColor: 'rgba(75, 192, 192, 0.2)', // Teal background
                borderColor: 'rgba(75, 192, 192, 1)',     // Teal border
                borderWidth: 1
                // --- End Styling ---
            }]
        },
        // --- Restore Options ---
        options: {
          indexAxis: 'x', // Companies on X axis
          scales: {
            y: {
              beginAtZero: true, // Start Y axis at 0
              title: { display: true, text: 'Number of Applications' } // Y axis title
            },
            x: {
              title: { display: true, text: 'Company' } // X axis title
            }
          },
          plugins: {
            legend: { display: true } // Show legend ('Applications per Company')
          }
        }
        // --- End Options ---
    };

    // 7. Render the chart
    console.log("Attempting to render final styled chart...");
    try {
        window.renderChart(chartData, this.container);
        console.log("Styled chart rendered successfully.");
        // dv.paragraph("Company Application Chart:"); // Optional title
    } catch (e) {
        console.error("Render error with styled chart:", e);
        dv.paragraph("⚠️ Error rendering styled chart: " + e.message);
    }
} else {
    dv.paragraph("ℹ️ No valid application data found after processing.");
    console.log("No data to render.");
}
```
#### To-Do:

```tasks
tags includes #jobhunt 
not done 
```

#### In-Flight: ![[Hunt/Board/In-Flight|In-Flight]]

#### To-Apply: ![[Hunt/Board/Pending|Pending]]

#### Applied: ![[Hunt/Board/Applied|Applied]]

#### Denied: ![[Hunt/Board/Denied|Denied]]