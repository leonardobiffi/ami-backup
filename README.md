# AMI Backup Lambda Function

> Serverless Framework Version: >= 2.27.0

Esta função é para criar a AMI como um backup para todas as instâncias necessárias com base nas tags e excluir as AMI mais antigas.

## Instalar Serverless Framework

https://www.serverless.com/framework/docs/install-standalone

```sh
curl -o- -L https://slss.io/install | bash
```

## Pré-requisitos

* A função Lambda usada requer acesso de leitura EC2, acesso total à AMI e acesso à marcação de recursos, essas permissões estão no arquivo PolicyAMIBackup.json 
* Todas as instâncias que precisam de backup da AMI têm para ser marcado e essa tag será usada pela função Lambda para identificar essas instâncias (aqui estamos usando a tag Key: Backup, Value: true) 
* As instâncias NÂO DEVEM TER A TAG NAME COM CARACTERES ESPECIAIS. (ex: ç ~ ´ ' ")


## Como funciona? 

### Backup da AMI

Isso excluirá as AMIs criadas por esse script e mais de um número de dias que você fornecer como entrada e criará a nova AMI para uma instância, e a mesma AMI será marcada pela busca de todas as tags da instância, duas tags extras DELETE_ON = yes e SNAPSHOT_TAG = yes serão foi adicionada uma ordem para identificar as AMIs durante a identificação de instantâneos e a exclusão de AMIs antigas, portanto, basicamente, qualquer AMI com DELETE_ON = yes será excluída quando você executar o script com base no número de dias que você fornecer para manter as AMIs. 

* tag DELETE_ON = yes é usado para identificar as AMI que devem ser excluídas após um determinado número de dias. 
* tag SNAPSHOT_TAG = yes é usado para identificar as AMIs das quais os snapshots precisam ser etiquetados.
* tag RetentionDays = 7 é usado para especificar o número de dias para a retenção da AMI. Se não houver uma tag na instância, será usado o padrão definido na função. 
* tag Backup = True é usada para marcar a instância para backup.

Depois que as capturas instantâneas forem identificadas, a tag SNAPSHOT_TAG = yes será excluída da AMI. 

### Exceção: 

* O script usa a notificação no Slack como manipulador de exceção, conforme sua conveniência e este é um parâmetro opcional, se você fornecer o parâmetro do Slack como "true", as exceções serão exibidas no Slack o mesmo da saída stdout. 


## Deploy

Para realizar o deploy da lambda no Cliente é necessário ter o awscli configurado com as Secret Keys da conta do cliente.

### Configurar arquivo .env

Criar cópia do arquivo .env.example, como .env.prod

```bash
cp .env.example .env.prod
```

Adicionar as informações para o Cliente que vai realizar o Deploy da função

### Dependências

Instalar plugins do serverless framework

```bash
serverless plugin install -n serverless-dotenv-plugin --stage prod
```

### Deploy

```bash
serverless deploy --stage prod
```

### Remover

```bash
serverless remove --stage prod
```
