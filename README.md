# SoonBody — recuperação em andamento

## Atualização: captura de e-mail removida do percurso

As duas conexões que levavam às telas de captura de e-mail agora levam diretamente à tela seguinte. A alteração está no espelho local; o site publicado não foi modificado. Para reaplicar depois de atualizar o espelho, execute `python skip_email.py` após `prepare_local.py`.

Os percursos feminino (40–49) e masculino (70+) foram percorridos novamente e chegaram ao resumo da oferta, após a raspadinha, com 47 telas capturadas em cada execução. Nenhuma compra foi iniciada. O opt-in de novidades foi recusado durante o teste. Os registros atuais estão nos arquivos run.json das pastas de captura. Ainda há erros de telemetria/endpoints ausentes; estes resultados não certificam o backend ou o pagamento.

As observações anteriores abaixo registram o estado anterior à retirada do e-mail.

Origem: https://soonbody.com/pt/flow-tai-chi-yoga-2

O servidor respondeu HTTP 200, com Cloudflare. A aplicação usa SvelteKit e inclui a definição de 94 nós do funil no HTML: 68 perguntas, 16 telas informativas, 6 resultados, 2 capturas de e-mail e 2 resumos. O indicador do percurso mostra 45 etapas.

## Executar

Nesta pasta, execute `python serve.py --site site --port 8000` e abra http://127.0.0.1:8000/pt/flow-tai-chi-yoga-2 . O servidor inclui fallback de SPA e um cabeçalho X-Mirror-Source para identificar a instância.

Para repetir a aquisição: `python mirror.py https://soonbody.com/pt/flow-tai-chi-yoga-2 --dest site`, seguido de `python prepare_local.py --site site`.

Auditoria: `python audit_assets.py --site site --check-remote`.

Para o crawler Python, instale Playwright (`python -m pip install playwright` e `python -m playwright install chromium`) e execute `python crawl.py --site site --url http://127.0.0.1:8000/pt/flow-tai-chi-yoga-2`.

## Evidências e limites atuais

- A aquisição recursiva encontrou 766 arquivos. Na auditoria anterior à última preparação, 765 referências estavam presentes, e sete caminhos restantes responderam HTTP 404 também na origem. São analytics.js, gtm.js, config.js e quatro caminhos de fonte de imagens já compiladas. A auditoria precisa ser repetida após qualquer alteração.
- Rotas de entrada e profundas responderam HTTP 200 com fallback de SPA.
- O percurso feminino 40–49 foi capturado até a tela de e-mail, etapa 45. O masculino 70+ também chegou à captura de e-mail, etapa 45. Cada tela tem HTML, texto, JSON e screenshot nas pastas capture_*.
- O avanço após o e-mail e a chegada ao resumo/compra ainda NÃO foram verificados. A causa da parada do crawler ainda não foi determinada. Não atribuir essa parada ao backend sem investigação adicional.
- As demais faixas etárias e todas as alternativas de resposta ainda NÃO foram verificadas.
- Há erros de console relativos a telemetria bloqueada e endpoints locais sem implementação. Não há confirmação de zero erros de console ou zero pedidos locais falhados.
- O inventário real do primeiro carregamento está em network_inventory.json, com método, tipo e URL de cada pedido observado. Ele inclui analytics e terceiros.

## Dependências para republicação

O HTML configura PUBLIC_API_URL como https://api.soonbody.com e PUBLIC_SESSION_BACKEND_V3 como https://session.soonbody.crm.wtf. O espelho contém apenas o cliente e os assets públicos; não contém o backend nem credenciais privadas.

No bundle ByMz1AkN.js há POST /session, PUT /session/{uuid}, GET /quiz/{uuid}, POST /payments/create-session e POST /payments/update-session. O cliente de pagamento contém integração Primer e implementações PayPal/Yuno compartilhadas. A configuração desta oferta tem paypalEnabled:false. A criação de sessão e a cobrança não foram executadas.

O bundle CaXFW32f.js contém POST /api/crm/an-v2/an e outros endpoints de analytics. CeMlYiZP.js contém /api/analytics/events e /api/analytics/events/batch. O inventário de rede confirma pedidos de telemetria antes de qualquer resposta ao quiz.

O HTML inclui Meta Pixel 1165879388928886 para o funil, um ID Meta padrão distinto (1426378168954859), GTM-NB94Z7VJ, um token público PostHog e Klaviyo TA9NeD. O inventário também observa Google Analytics/Ads, Pinterest, AppLovin e outros terceiros. Ativação de gravação de sessão, todos os IDs e a associação às contas precisam de verificação adicional.

A entidade interna é identificada apenas como legalEntity:soonbody e o domínio de suporte como contact-us.soonbody.com. Nome jurídico completo, endereço e textos legais ainda precisam de conferência.

O servidor local usa CSP para restringir conexões externas. Essa configuração é para inspeção local; qualquer publicação exige configurar conscientemente backend, pagamentos, analytics e documentos legais. Este pacote ainda não está certificado como pronto para republicar.


Atualização: telas de novidades por e-mail e raspadinha removidas do percurso nos dois ramos. A análise segue diretamente para a oferta. As capturas anteriores registram a versão antiga.
