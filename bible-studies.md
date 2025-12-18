---
layout: default
title: Bible Studies
permalink: /bible-studies/
---

<div class="main-content">
  <ul class="post-list">
    {% assign sorted_studies = site.bible_studies | sort: "date" | reverse %}
    {% for study in sorted_studies %}
      <li>
        <div class="post-item">
          {% if study.date %}
          <span class="post-date">{{ study.date | date: "%Y.%m.%d" }}</span>
          {% endif %}
          <a class="post-title" href="{{ study.url | relative_url }}">{{ study.title }}</a>
          {% if study.scripture %}
          <span class="post-meta">{{ study.scripture }}</span>
          {% endif %}
        </div>
      </li>
    {% endfor %}
  </ul>
</div>

