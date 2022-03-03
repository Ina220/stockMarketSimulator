
new Chart(document.getElementById("myChart"), {
     type: 'line',
      data: {
        labels: {{labelsMin | tojson}},
        datasets: [{
          label: "Month",
          backgroundColor: {{colors | tojson}},
        data: {{values | tojson}}
        }]
      },
      options: {
        title: {
          display: true,
          text: 'Stock price Chart'
        }
      }
    });
