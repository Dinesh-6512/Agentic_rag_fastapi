import { useState, useEffect, useRef } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { fetchApi } from '../api';
import './ProductAssistant.css';

export default function ProductAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [activeProduct, setActiveProduct] = useState(null);
  
  const location = useLocation();
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Scroll to bottom whenever messages or loading changes
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  }, [isOpen]);

  // Detect route changes to set product context
  useEffect(() => {
    const match = location.pathname.match(/^\/product\/(\d+)$/);
    if (match) {
      const productId = parseInt(match[1], 10);
      fetchApi(`/products/${productId}`)
        .then(product => {
          if (product && product.id) {
            setActiveProduct({ id: product.id, name: product.name });
          }
        })
        .catch(() => {
          // If error fetching product, leave activeProduct as is or fallback
        });
    } else {
      // Browsing general store pages
      setActiveProduct(null);
    }
  }, [location.pathname]);

  // Listen for custom trigger from product details page
  useEffect(() => {
    const handleOpenEvent = (event) => {
      const detail = event.detail || {};
      if (detail.product_id) {
        setActiveProduct({
          id: detail.product_id,
          name: detail.product_name || `Product #${detail.product_id}`
        });
      }
      setIsOpen(true);
    };

    window.addEventListener('open-rag-assistant', handleOpenEvent);
    return () => {
      window.removeEventListener('open-rag-assistant', handleOpenEvent);
    };
  }, []);

  const handleClearContext = (e) => {
    e.stopPropagation();
    setActiveProduct(null);
  };

  const handleSend = async (questionText) => {
    const q = (questionText || input).trim();
    if (!q || isLoading) return;

    // Add user message
    const userMsg = {
      id: Date.now(),
      sender: 'user',
      text: q
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    // Check auth token before request
    const token = localStorage.getItem('token');
    if (!token) {
      setIsLoading(false);
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'assistant',
          isAuthError: true,
          status: 'error',
          text: 'Please log in to your account to use the Product Knowledge Assistant.'
        }
      ]);
      return;
    }

    try {
      const payload = {
        question: q,
        product_id: activeProduct ? activeProduct.id : null
      };

      const response = await fetchApi('/rag/ask', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      let sourceText = '';
      if (Array.isArray(response.sources) && response.sources.length > 0) {
        sourceText = response.sources.join(', ');
      } else if (response.source) {
        sourceText = response.source;
      }

      const assistantMsg = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: response.answer,
        status: response.status,
        source: sourceText,
        traceId: response.observability?.trace_id || response.trace_id,
        latencyMs: Math.round(response.observability?.total_time_ms || response.total_latency_ms || 0)
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      console.error('RAG Assistant request error:', err);
      const isAuth = err.status === 401 || (err.message && err.message.toLowerCase().includes('authenticat'));
      
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'assistant',
          isAuthError: isAuth,
          status: 'error',
          text: isAuth
            ? 'Please log in to your account to use the Product Knowledge Assistant.'
            : (err.message || 'Unable to reach the knowledge assistant. Please check your connection and try again.')
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleSend();
  };

  // Helper suggestion questions
  const getSuggestions = () => {
    if (activeProduct) {
      return [
        `How do I set up and pair this device?`,
        `What are the battery and charging specifications?`,
        `How do I troubleshoot connection or performance issues?`
      ];
    }
    return [
      `How do I pair the Lumina Wireless Mouse?`,
      `Is the Apex Pro Watch waterproof and how do I charge it?`,
      `How do I enable Active Noise Cancellation on the Aura Sound Headphones?`
    ];
  };

  return (
    <>
      {/* Floating Entry Point Launcher */}
      {!isOpen && (
        <button
          id="rag-assistant-launcher"
          className="assistant-launcher"
          onClick={() => setIsOpen(true)}
          aria-label="Open Product Knowledge Assistant"
        >
          <span className="assistant-launcher-icon">💬</span>
          <span>Ask Assistant</span>
        </button>
      )}

      {/* Floating Card / Slide-over Drawer Window */}
      {isOpen && (
        <div id="rag-assistant-window" className="assistant-window">
          {/* Header Zone */}
          <div className="assistant-header">
            <div className="assistant-header-top">
              <div className="assistant-title-group">
                <span className="assistant-title-icon">💬</span>
                <h3 className="assistant-title">Product Assistant</h3>
                <span className="assistant-badge">RAG Active</span>
              </div>
              <button
                id="rag-assistant-close"
                className="assistant-close-btn"
                onClick={() => setIsOpen(false)}
                aria-label="Close Assistant"
              >
                ✕
              </button>
            </div>

            {/* Context Chip */}
            {activeProduct ? (
              <div id="rag-active-context-chip" className="assistant-context-chip product-active">
                <span>🏷️ Active Context: <strong>{activeProduct.name}</strong></span>
                <button
                  id="rag-clear-context-btn"
                  className="assistant-context-clear"
                  onClick={handleClearContext}
                  title="Clear product context and ask store-wide"
                  aria-label="Clear context"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div id="rag-global-context-chip" className="assistant-context-chip global-scope">
                <span>📚 Scope: All Store Product Manuals</span>
              </div>
            )}
          </div>

          {/* Messages Scrollable Zone */}
          <div className="assistant-messages" id="rag-messages-container">
            {messages.length === 0 && (
              <div className="assistant-welcome">
                <h4>✨ Knowledge Assistant Ready</h4>
                <p>
                  I provide grounded answers directly from our verified product manuals and technical documentation.
                </p>
                <div className="assistant-suggestions">
                  <span style={{ fontSize: '0.78rem', color: '#64748b' }}>Suggested questions:</span>
                  {getSuggestions().map((suggestion, idx) => (
                    <button
                      key={idx}
                      className="assistant-suggestion-pill"
                      onClick={() => handleSend(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => {
              if (msg.sender === 'user') {
                return (
                  <div key={msg.id} className="message-user-wrap">
                    <div className="message-user">{msg.text}</div>
                  </div>
                );
              }

              // Assistant states
              let stateClass = '';
              let stateIcon = '';
              if (msg.isAuthError || msg.status === 'error') {
                stateClass = 'state-error';
                stateIcon = msg.isAuthError ? '🔒 ' : '⚠️ ';
              } else if (msg.status === 'no_information_found') {
                stateClass = 'state-no-data';
                stateIcon = 'ℹ️ ';
              } else if (msg.status === 'clarification_needed') {
                stateClass = 'state-clarification';
                stateIcon = '❓ ';
              } else if (msg.status === 'security_refusal') {
                stateClass = 'state-security';
                stateIcon = '🛡️ ';
              }

              return (
                <div key={msg.id} className="message-assistant-wrap">
                  <div className={`message-assistant ${stateClass}`}>
                    {stateIcon && <span>{stateIcon}</span>}
                    {msg.text}

                    {msg.isAuthError && (
                      <div>
                        <Link to="/login" className="assistant-auth-action">
                          Log In to Continue
                        </Link>
                      </div>
                    )}
                  </div>

                  {/* Grounded Source Citation Area */}
                  {msg.source && (
                    <div className="assistant-source-badge" title="Verified source document">
                      <span className="source-icon">📄</span>
                      <span>Source: {msg.source}</span>
                    </div>
                  )}

                  {/* Observability Tag */}
                  {msg.latencyMs && (
                    <div className="assistant-obs-tag">
                      <span>⚡ {msg.latencyMs}ms</span>
                      {msg.traceId && <span>• ID: {msg.traceId.slice(0, 8)}</span>}
                    </div>
                  )}
                </div>
              );
            })}

            <div ref={messagesEndRef} />
          </div>

          {/* Status / Loading Feedback Zone */}
          {isLoading && (
            <div id="rag-loading-indicator" className="assistant-loading-indicator">
              <span>⚡ Searching approved product manuals</span>
              <div className="loading-spinner-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}

          {/* Input Zone */}
          <div className="assistant-input-zone">
            <form className="assistant-form" onSubmit={handleSubmit}>
              <input
                ref={inputRef}
                id="rag-question-input"
                type="text"
                className="assistant-input"
                placeholder={
                  activeProduct
                    ? `Ask about setup, specs, or troubleshooting for this item...`
                    : `Ask about any product manual (e.g. 'How do I pair the mouse?')...`
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={isLoading}
                autoComplete="off"
              />
              <button
                id="rag-send-btn"
                type="submit"
                className="assistant-send-btn"
                disabled={!input.trim() || isLoading}
                aria-label="Send question"
              >
                ➔
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
