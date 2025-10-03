
// ChatWidget.jsx - React functional component using Flowise embed script
import React, { useEffect } from "react";

const ChatWidget = ({ user }) => {
  useEffect(() => {
    const script = document.createElement("script");
    script.src = `${user.host.replace(/\/+$/, "")}/embed.min.js`;
    script.async = true;
    script.onload = () => {
      if (!window.Flowise || !window.Flowise.initFull) {
        console.warn("Flowise embed script not available");
        return;
      }
      window.Flowise.initFull({
        chatflowid: user.id, // chatflow id passed in user.id per your example
        apiHost: user.host,
        target: "#flowise-chatbot",
        chatflowConfig: {
          sessionId: (user.sessionId || "static-session-001").toString(),
          vars: {
            userId: user.userId || user.id,
            userName: user.userName || user.name,
            userEmail: user.userEmail || user.email,
            currentUrl: window.location.href,
            userRole: "authenticated"
          }
        }
      });
    };
    script.onerror = () => console.error("Failed to load Flowise embed script");
    document.body.appendChild(script);
    return () => {
      // cleanup: remove script (optional)
      try { document.body.removeChild(script); } catch(e) {}
      // if Flowise exposes a destroy API, call it here (not standardized)
    };
  }, [user]);

  return <div id="flowise-chatbot" style={{height: "100%", width: "100%"}} />;
};

export default ChatWidget;
