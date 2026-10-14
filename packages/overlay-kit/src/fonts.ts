import {loadFont} from "@remotion/fonts";
import {cancelRender, continueRender, delayRender, staticFile} from "remotion";

const handle = delayRender("Loading JetBrains Mono and Bebas Neue");

Promise.all([
  loadFont({
    family: "JetBrains Mono",
    url: staticFile("fonts/JetBrainsMono-Regular.woff2"),
    weight: "400",
    format: "woff2",
  }),
  loadFont({
    family: "JetBrains Mono",
    url: staticFile("fonts/JetBrainsMono-Bold.woff2"),
    weight: "700",
    format: "woff2",
  }),
  loadFont({
    family: "Bebas Neue",
    url: staticFile("fonts/BebasNeue-Regular.woff2"),
    weight: "400",
    format: "woff2",
  }),
])
  .then(() => continueRender(handle))
  .catch((error) => cancelRender(error));
