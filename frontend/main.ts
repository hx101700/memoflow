import { createApp } from "vue";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";
import "./style.css";
import App from "./App.vue";
import ReviewApp from "./ReviewApp.vue";
import { createReviewApi } from "./review";
import { createApi } from "./api";
import type { Language } from "./types";
import type { Translate } from "./i18n";

if (window.location.pathname === "/review") {
  createApp(ReviewApp, { connect: (language: () => Language, t: Translate) => createReviewApi(window.fetch.bind(window), language, t) }).mount("#app");
} else {
  createApp(App, { connect: (language: () => Language, t: Translate) => createApi(window.fetch.bind(window), language, t) }).mount("#app");
}
