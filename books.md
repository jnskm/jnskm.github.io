---
layout: default
title: "Books"
permalink: /books/
---

<div class="main-content">
  <h2>Tails of Grace Series</h2>
  <ul class="post-list">
    {% assign tails_books = site.books | where: "series", "Tails of Grace" | sort: "date" %}
    {% for book in tails_books %}
      <li>
        <div class="post-item">
          <a class="post-title" href="{{ book.url | relative_url }}">{{ book.title }}</a>
        </div>
      </li>
    {% endfor %}
  </ul>
</div>