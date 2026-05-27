import { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Tracklist",
    short_name: "Tracklist",
    description: "Rate the albums you love. Share your taste.",
    start_url: "/",
    display: "standalone",
    background_color: "#0D0D0D",
    theme_color: "#0D0D0D",
    orientation: "portrait",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    categories: ["music", "entertainment", "social"],
    shortcuts: [
      {
        name: "Search Albums",
        short_name: "Search",
        description: "Find albums to rate",
        url: "/search",
      },
      {
        name: "Charts",
        short_name: "Charts",
        description: "See what's trending",
        url: "/charts",
      },
    ],
  };
}
