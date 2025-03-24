const articles = [
  {
    title: "SensorThings Utils",
    description: "OGC SensorThings Compliant Building Sensor Database",
    link: "https://multicare.bk.tudelft.nl/st-utils"
  },
  {
    title: "FROST Server API",
    description: "Building Sensor Database, FROST API.",
    link: "https://multicare.bk.tudelft.nl/FROST-Server"
  }
];

function createArticleCard(article) {
  const li = document.createElement('li');
  li.className = 'article-card';
  
  li.innerHTML = `
    <div class="article-content">
      <h3>${article.title}</h3>
      <p>${article.description}</p>
    </div>
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
      <polyline points="15 3 21 3 21 9"/>
      <line x1="10" y1="14" x2="21" y2="3"/>
    </svg>
  `;

  li.addEventListener('click', () => {
    window.location.href = article.link;
  });

  return li;
}

document.addEventListener('DOMContentLoaded', () => {
  const articleList = document.getElementById('articleList');
  articles.forEach(article => {
    articleList.appendChild(createArticleCard(article));
  });
});
